import http.client
import json
from pathlib import Path
import shutil
import threading
import time
import pytest
import settings
from restore import Handler, Jobs, ThreadingHTTPServer, read_json
from file_io import atomic_json


@pytest.fixture
def server(tmp_path):
    config = settings.load(local=False)
    config["output_dir"] = str(tmp_path)
    jobs = Jobs(config, check=False)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.jobs = jobs
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, jobs
    jobs.cancel()
    httpd.shutdown()
    httpd.server_close()
    thread.join(2)


def request(server, path, method="GET", body=None, headers=None):
    httpd, _ = server
    connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=10)
    connection.request(method, path, body, headers or {})
    response = connection.getresponse()
    data = response.read()
    info = dict(response.getheaders())
    status = response.status
    connection.close()
    return status, data, info


def test_real_index_and_headers(server):
    status, data, headers = request(server, "/")
    assert status == 200 and b"Choose audio" in data
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"


@pytest.mark.parametrize("missing", ["ffmpeg", "ffprobe"])
def test_preflight_reports_each_required_audio_tool(monkeypatch, missing):
    real_which = shutil.which

    def which(name):
        if name in {"ffmpeg", "ffprobe"}:
            return None if name == missing else "installed-tool"
        return real_which(name)

    monkeypatch.setattr(shutil, "which", which)
    issues = settings.preflight(settings.load(local=False))
    tool_issues = [
        issue for issue in issues if "PATH" in issue and "ff" in issue.lower()
    ]
    assert len(tool_issues) == 1
    assert missing in tool_issues[0].lower()


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example"},
        {"Origin": "https://evil.example"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_reject_foreign_requests(server, headers):
    assert request(server, "/api/session", headers=headers)[0] == 403


def test_mutations_need_session_token(server):
    assert request(server, "/api/jobs?name=test.wav", "POST", b"hello")[0] == 403


def test_upload_validation_and_single_job(server, monkeypatch):
    _, jobs = server
    started = []
    monkeypatch.setattr(jobs, "start", lambda path: started.append(path))
    headers = {"X-Restore-Token": jobs.token}
    assert (
        request(server, "/api/jobs?name=file.exe", "POST", b"wrong", headers)[0] == 400
    )
    status, data, _ = request(
        server, "/api/jobs?name=..%2F..%2Fvoice.wav", "POST", b"audio", headers
    )
    assert status == 202
    identifier = json.loads(data)["id"]
    directory = jobs.directory(identifier)
    assert (directory / "upload.wav").read_bytes() == b"audio"
    assert jobs.status(identifier)["name"] == "voice.wav"
    assert len(started) == 1
    assert (
        request(server, "/api/jobs?name=again.wav", "POST", b"audio", headers)[0] == 409
    )


def test_ranges_and_media_allowlist(server):
    _, jobs = server
    directory, _ = jobs.reserve("voice.wav")
    (directory / "original.wav").write_bytes(b"0123456789")
    path = f"/media/{directory.name}/original/wav"
    status, data, headers = request(server, path, headers={"Range": "bytes=2-5"})
    assert (
        status == 206 and data == b"2345" and headers["Content-Range"] == "bytes 2-5/10"
    )
    assert request(server, path, headers={"Range": "bytes=-3"})[1] == b"789"
    assert request(server, path, headers={"Range": "bytes=20-"})[0] == 416
    assert request(server, f"/media/{directory.name}/config/json")[0] == 404
    assert request(server, "/../config.json")[0] == 404


def test_cancel_then_resume_keeps_upload(server, monkeypatch):
    _, jobs = server
    directory, _ = jobs.reserve("voice.wav")
    (directory / "upload.wav").write_bytes(b"audio")
    jobs.cancel(directory.name)
    assert jobs.status(directory.name)["status"] == "cancelled" and jobs.active is None
    resumed = []
    monkeypatch.setattr(jobs, "start", lambda path: resumed.append(path))
    jobs.resume(directory.name)
    assert resumed == [directory]


def test_interrupted_job_detection(tmp_path):
    config = settings.load(local=False)
    config["output_dir"] = str(tmp_path)
    jobs = Jobs(config, check=False)
    directory, _ = jobs.reserve("voice.wav")
    recovered = Jobs(config, check=False)
    assert recovered.status(directory.name)["status"] == "interrupted"


def test_crashed_worker_becomes_visible_failure(server):
    _, jobs = server
    directory, _ = jobs.reserve("voice.wav")

    class Dead:
        def wait(self):
            return -1073741819

    process = Dead()
    jobs.process = process
    jobs.watch(directory, process)
    assert jobs.status(directory.name)["status"] == "failed"
    assert "-1073741819" in jobs.status(directory.name)["message"]
    assert jobs.active is None


def test_profile_configuration_is_explicit(tmp_path):
    config = settings.load(local=False)
    assert config["dsp"]["declick"]["click_repair"]["engine"] == "waves"
    assert config["studio_finish"]["amount"] == 0.35
    config["profile"] = "portable"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    portable = settings.load(path)
    assert not portable["breath_control"]["nectar_enabled"]
    assert not portable["studio_finish"]["soothe_enabled"]
    assert portable["dsp"]["declick"]["click_repair"]["engine"] == "audiojs"


@pytest.mark.parametrize("value", [0, 65, True, 2.5])
def test_invalid_threads_rejected(tmp_path, value):
    config = settings.load(local=False)
    config["runtime"]["inference_params"]["cpu_threads"] = value
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        settings.load(path)


def test_local_override_does_not_mutate_base(tmp_path):
    shutil.copyfile(settings.ROOT / "config.json", tmp_path / "config.json")
    (tmp_path / ".config.local.json").write_text(
        json.dumps({"studio_finish": {"amount": 0.2}})
    )
    assert settings.load(tmp_path / "config.json")["studio_finish"]["amount"] == 0.2
    assert (
        settings.load(tmp_path / "config.json", local=False)["studio_finish"]["amount"]
        == 0.35
    )


def test_only_one_server_can_manage_output_folder(tmp_path):
    from restore import runtime_lock

    first = runtime_lock(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="already running"):
            runtime_lock(tmp_path)
    finally:
        first.close()
    second = runtime_lock(tmp_path)
    second.close()


def test_cancel_terminates_only_owned_worker_tree(server, tmp_path, monkeypatch):
    import psutil

    _, jobs = server
    (tmp_path / "worker.py").write_text(
        'import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"])\nPath(sys.argv[1],"child.pid").write_text(str(p.pid))\ntime.sleep(30)\n'
    )
    monkeypatch.setattr(settings, "ROOT", tmp_path)
    directory, _ = jobs.reserve("voice.wav")
    (directory / "upload.wav").write_bytes(b"test")
    jobs.start(directory)
    process = jobs.process
    deadline = time.monotonic() + 8
    while not (directory / "child.pid").is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert (directory / "child.pid").is_file()
    child = int((directory / "child.pid").read_text())
    jobs.cancel(directory.name)
    assert process.poll() is not None and not psutil.pid_exists(child)
    assert jobs.status(directory.name)["status"] == "cancelled"


def test_parent_watchdog_marks_job_interrupted(tmp_path):
    import os, subprocess, sys

    atomic_json(tmp_path / "state.json", {"status": "running"})
    env = dict(
        os.environ, RESTORE_PARENT_PID=str(os.getpid()), RESTORE_PARENT_CREATED="-1"
    )
    code = "import sys,threading;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from worker import guard_parent;guard_parent(Path(sys.argv[2]),threading.Event())"
    process = subprocess.run(
        [sys.executable, "-c", code, str(settings.ROOT), str(tmp_path)],
        env=env,
        timeout=10,
    )
    assert process.returncode == 130
    assert read_json(tmp_path / "state.json")["status"] == "interrupted"
