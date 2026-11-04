"""Restore's loopback-only web app. No upload leaves this computer."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
import argparse
import atexit
import hashlib
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser

import settings

sys.path.insert(0, str(settings.ROOT / "engine"))
from file_io import atomic_json

EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aif", ".aiff"}
MAX_UPLOAD = 512 * 1024 * 1024
STAGES = ["01-denoise", "02-dereverb", "03-breaths", "04-mouth", "05-finish", "cleaned"]
ACTIVE = {"uploading", "starting", "running"}


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


class Jobs:
    def __init__(self, config, check=True):
        self.config = config
        self.root = Path(config["output_dir"])
        self.root.mkdir(parents=True, exist_ok=True)
        self.issues = settings.preflight(config) if check else []
        self.lock = threading.RLock()
        self.process = None
        self.active = None
        self.token = secrets.token_urlsafe(32)
        for directory in self.root.iterdir():
            state = read_json(directory / "state.json") if directory.is_dir() else None
            if state and state.get("status") in ACTIVE:
                state.update(
                    status="interrupted",
                    message="Restore was closed. Resume to reuse verified stages.",
                )
                atomic_json(directory / "state.json", state)

    def directory(self, identifier):
        if not re.fullmatch("[a-f0-9]{32}", identifier):
            raise ValueError("Unknown recording")
        directory = self.root / identifier
        if not (directory / "state.json").is_file():
            raise ValueError("Unknown recording")
        return directory

    def status(self, identifier):
        directory = self.directory(identifier)
        state = read_json(directory / "state.json", {})
        receipt = read_json(directory / "result/receipt.json", {})
        state["stages_complete"] = len(receipt.get("stages", []))
        state["current_stage"] = receipt.get("current_stage", "preparing")
        if state.get("status") in ACTIVE:
            state["elapsed_seconds"] = max(
                0, time.time() - state.get("started_at", time.time())
            )
        if state.get("status") == "complete":
            state["metrics"] = receipt.get("output_metrics", {})
            state["cpu_core_seconds"] = receipt.get("total_cpu_core_seconds", 0)
        return state

    def recent(self):
        found = []
        for p in self.root.glob("*/state.json"):
            state = read_json(p, {})
            if state.get("id"):
                found.append(state)
        return sorted(found, key=lambda x: x.get("created_at", 0), reverse=True)[:8]

    def reserve(self, name):
        name = Path(name.replace("\\", "/")).name[:160]
        ext = Path(name).suffix.lower()
        if ext not in EXTENSIONS:
            raise ValueError("Choose WAV, MP3, FLAC, M4A, OGG or AIFF audio.")
        with self.lock:
            if self.active:
                raise RuntimeError("Another recording is already being cleaned.")
            if self.issues:
                raise ValueError(
                    "Finish setup before cleaning: " + "; ".join(self.issues)
                )
            identifier = uuid.uuid4().hex
            directory = self.root / identifier
            directory.mkdir()
            self.active = identifier
            atomic_json(directory / "config.json", self.config)
            atomic_json(
                directory / "state.json",
                dict(
                    id=identifier,
                    name=name,
                    extension=ext,
                    created_at=time.time(),
                    started_at=time.time(),
                    status="uploading",
                    message="Receiving recording",
                ),
            )
            return directory, ext

    def start(self, directory):
        with self.lock:
            state = read_json(directory / "state.json")
            if self.active and self.active != directory.name:
                raise RuntimeError("Another recording is already being cleaned.")
            state.update(
                status="starting",
                started_at=time.time(),
                message="Starting the fixed workflow",
            )
            atomic_json(directory / "state.json", state)
            self.active = directory.name
            env = dict(
                os.environ,
                PYTHONIOENCODING="utf-8",
                PYTHONUTF8="1",
                PYTHONFAULTHANDLER="1",
            )
            import psutil

            env.update(
                RESTORE_PARENT_PID=str(os.getpid()),
                RESTORE_PARENT_CREATED=str(psutil.Process().create_time()),
            )
            try:
                with (directory / "worker.log").open("a", encoding="utf-8") as log:
                    self.process = subprocess.Popen(
                        [
                            sys.executable,
                            str(settings.ROOT / "worker.py"),
                            str(directory),
                        ],
                        cwd=settings.ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env=env,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except OSError:
                self.fail(directory, "Could not start the audio worker.")
                raise
            threading.Thread(
                target=self.watch, args=(directory, self.process), daemon=True
            ).start()

    def watch(self, directory, process):
        code = process.wait()
        with self.lock:
            state = read_json(directory / "state.json", {})
            if state.get("status") in ACTIVE:
                state.update(
                    status="failed",
                    message=f"Audio worker exited ({code}). Saved stages can be resumed; details are in worker.log.",
                )
                atomic_json(directory / "state.json", state)
            if self.process is process:
                self.active = self.process = None

    def fail(self, directory, message):
        with self.lock:
            state = read_json(directory / "state.json", {})
            state.update(status="failed", message=message)
            atomic_json(directory / "state.json", state)
            if self.active == directory.name:
                self.active = None

    def resume(self, identifier):
        with self.lock:
            if self.active:
                raise RuntimeError("Another recording is already being cleaned.")
            directory = self.directory(identifier)
            if self.status(identifier)["status"] not in {
                "failed",
                "cancelled",
                "interrupted",
            }:
                raise ValueError("Only stopped jobs can be resumed.")
            if not any(directory.glob("upload.*")):
                raise ValueError("Upload this recording again.")
            self.start(directory)

    def cancel(self, identifier=None):
        import psutil

        with self.lock:
            if not self.active or (identifier and identifier != self.active):
                return
            directory = self.directory(self.active)
            process = self.process
            if process and process.poll() is None:
                try:
                    parent = psutil.Process(process.pid)
                    owned = parent.children(recursive=True) + [parent]
                    for p in reversed(owned):
                        try:
                            p.terminate()
                        except psutil.NoSuchProcess:
                            pass
                    _, alive = psutil.wait_procs(owned, timeout=4)
                    for p in alive:
                        try:
                            p.kill()
                        except psutil.NoSuchProcess:
                            pass
                    psutil.wait_procs(alive, timeout=3)
                except psutil.NoSuchProcess:
                    pass
            state = read_json(directory / "state.json", {})
            state.update(
                status="cancelled",
                message="Stopped. Completed stages are saved for Resume.",
            )
            atomic_json(directory / "state.json", state)
            self.active = self.process = None


class Handler(BaseHTTPRequestHandler):
    server_version = "Restore/2.0"

    def log_message(self, *_):
        pass

    def trusted(self, mutation=False):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://{host}" for host in allowed}:
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            return False
        return not mutation or secrets.compare_digest(
            self.headers.get("X-Restore-Token", ""), self.server.jobs.token
        )

    def response_headers(self, status, kind, size, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def json(self, value, status=200):
        data = json.dumps(value, ensure_ascii=True).encode()
        self.response_headers(status, "application/json", len(data))
        self.wfile.write(data)

    def send_file(self, path, filename=None):
        if not path.is_file():
            return self.json({"error": "File is not ready."}, 404)
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        extra = {"Accept-Ranges": "bytes"}
        requested = self.headers.get("Range")
        if requested:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            if not match or not any(match.groups()):
                return self.json({"error": "Invalid range"}, 416)
            a, b = match.groups()
            if a:
                start = int(a)
                end = min(int(b), end) if b else end
            else:
                start = max(0, size - int(b))
            if start > end or start >= size:
                self.response_headers(
                    416,
                    "application/octet-stream",
                    0,
                    {"Content-Range": f"bytes */{size}"},
                )
                return
            status = 206
            extra["Content-Range"] = f"bytes {start}-{end}/{size}"
        if filename:
            extra["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(
                filename, safe=""
            )
        self.response_headers(
            status,
            mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            end - start + 1,
            extra,
        )
        with path.open("rb") as handle:
            handle.seek(start)
            left = end - start + 1
            while left:
                data = handle.read(min(65536, left))
                if not data:
                    break
                self.wfile.write(data)
                left -= len(data)

    def do_GET(self):
        if not self.trusted():
            return self.json({"error": "Local app access only."}, 403)
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        jobs = self.server.jobs
        try:
            if url.path == "/api/health":
                identity = hashlib.sha256(
                    (str(settings.ROOT.resolve()) + "|" + str(jobs.root.resolve()))
                    .lower()
                    .encode()
                ).hexdigest()[:16]
                return self.json(
                    {"app": "restore", "version": "2.0.1", "instance": identity}
                )
            if url.path == "/api/session":
                return self.json(
                    dict(
                        token=jobs.token,
                        profile=jobs.config["profile"],
                        issues=jobs.issues,
                        active=jobs.active,
                        recent=jobs.recent(),
                        version="2.0.1",
                    )
                )
            if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                return self.json(jobs.status(parts[2]))
            if len(parts) == 4 and parts[0] == "media":
                identifier, kind, extension = parts[1:]
                directory = jobs.directory(identifier)
                mapping = {
                    ("original", "wav"): directory / "original.wav",
                    ("cleaned", "wav"): directory / "result/cleaned.wav",
                    ("cleaned", "mp3"): directory / "result/cleaned.mp3",
                }
                path = mapping.get((kind, extension))
                if path is None or (
                    kind == "cleaned"
                    and jobs.status(identifier)["status"] != "complete"
                ):
                    return self.json({"error": "Audio is not ready."}, 404)
                name = Path(jobs.status(identifier)["name"]).stem
                return self.send_file(
                    path,
                    f"{name}-cleaned.{extension}"
                    if "download" in parse_qs(url.query)
                    else None,
                )
            assets = {
                "/": "index.html",
                "/app.js": "app.js",
                "/style.css": "style.css",
                "/icon.svg": "icon.svg",
            }
            if url.path in assets:
                return self.send_file(settings.ROOT / "web" / assets[url.path])
            return self.json({"error": "Not found"}, 404)
        except ValueError as exc:
            return self.json({"error": str(exc)}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        if not self.trusted(True):
            return self.json({"error": "Reload Restore to reconnect securely."}, 403)
        url = urlparse(self.path)
        parts = url.path.strip("/").split("/")
        jobs = self.server.jobs
        directory = None
        try:
            if url.path == "/api/jobs":
                if self.headers.get("Transfer-Encoding"):
                    raise ValueError("Content length required")
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_UPLOAD:
                    raise ValueError("Choose a file smaller than 512 MB.")
                name = parse_qs(url.query).get("name", ["recording.wav"])[0]
                directory, ext = jobs.reserve(name)
                self.connection.settimeout(120)
                temporary = directory / "upload.part"
                with temporary.open("wb") as output:
                    left = length
                    while left:
                        data = self.rfile.read(min(65536, left))
                        if not data:
                            raise ValueError(
                                "Upload interrupted; choose the file again."
                            )
                        output.write(data)
                        left -= len(data)
                temporary.replace(directory / ("upload" + ext))
                if jobs.status(directory.name)["status"] == "cancelled":
                    return self.json(jobs.status(directory.name), 202)
                jobs.start(directory)
                return self.json({"id": directory.name}, 202)
            if (
                len(parts) == 4
                and parts[:2] == ["api", "jobs"]
                and parts[3] in {"cancel", "resume"}
            ):
                jobs.directory(parts[2])
                if parts[3] == "cancel":
                    jobs.cancel(parts[2])
                else:
                    jobs.resume(parts[2])
                return self.json(jobs.status(parts[2]), 202)
            return self.json({"error": "Not found"}, 404)
        except RuntimeError as exc:
            return self.json({"error": str(exc)}, 409)
        except (ValueError, OSError) as exc:
            if directory:
                jobs.fail(
                    directory, "Upload or startup failed. Choose the recording again."
                )
            return self.json({"error": str(exc)}, 400)


def runtime_lock(root):
    """Prevent two servers from changing the same saved jobs."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / ".restore.lock").open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError(
            "Restore is already running with this output folder. Open its browser window."
        ) from None
    return handle


def serve(config=None, port=8530, open_browser=True, owner=None):
    config = config or settings.load()
    lock = runtime_lock(config["output_dir"])
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        jobs = Jobs(config)
    except Exception:
        lock.close()
        raise
    server.daemon_threads = True
    server.jobs = jobs
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Restore is ready at {url}", flush=True)
    atexit.register(jobs.cancel)
    if open_browser:
        webbrowser.open(url)
    done = threading.Event()
    if owner:

        def watch_owner():
            import psutil

            while not done.wait(2):
                try:
                    if psutil.Process(owner[0]).create_time() == owner[1]:
                        continue
                except psutil.NoSuchProcess:
                    pass
                server.shutdown()
                return

        threading.Thread(target=watch_owner, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        done.set()
        jobs.cancel()
        server.server_close()
        lock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8530)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--owner-pid", type=int)
    parser.add_argument("--owner-created", type=float)
    args = parser.parse_args()
    owner = (
        (args.owner_pid, args.owner_created)
        if args.owner_pid and args.owner_created
        else None
    )
    serve(settings.load(args.config), args.port, not args.no_browser, owner)
