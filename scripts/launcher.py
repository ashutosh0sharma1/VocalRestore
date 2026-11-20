"""Small optional Windows launcher. Does not embed Python audio dependencies."""

from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--desktop-owner", type=int)
    args = parser.parse_args()
    here = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[1]
    )
    config_path = here / "restore-launcher.json"
    config = (
        json.loads(config_path.read_text(encoding="utf-8"))
        if config_path.is_file()
        else {}
    )
    app = Path(args.app or config.get("app_dir", here)).resolve()
    python = Path(
        args.python or config.get("python", app / ".venv/Scripts/python.exe")
    ).resolve()
    if not (app / "restore.py").is_file() or not python.is_file():
        raise ValueError(
            "Restore source/Python environment missing. See README or restore-launcher.json."
        )
    spec = importlib.util.spec_from_file_location(
        "restore_settings", app / "settings.py"
    )
    settings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(settings)
    loaded = settings.load()
    identity = hashlib.sha256(
        (str(app) + "|" + str(Path(loaded["output_dir"]).resolve())).lower().encode()
    ).hexdigest()[:16]

    def healthy(port):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/health", timeout=0.25
            ) as response:
                info = json.load(response)
                return info.get("app") == "restore" and info.get("instance") == identity
        except (OSError, ValueError):
            return False

    def announce(port):
        import psutil
        lease = Path(loaded["output_dir"]) / f".desktop-{args.desktop_owner}"
        lease.write_text(str(psutil.Process(args.desktop_owner).create_time()), encoding="ascii")
        print(json.dumps({"url": f"http://127.0.0.1:{port}", "jobs": loaded["output_dir"]}), flush=True)

    for port in range(8530, 8555):
        if healthy(port):
            if args.desktop_owner:
                announce(port)
            elif not args.no_browser:
                webbrowser.open(f"http://127.0.0.1:{port}")
            print(f"Restore is already running at http://127.0.0.1:{port}", flush=True)
            return 0
    port = None
    for candidate in range(8530, 8555):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
                port = candidate
                break
            except OSError:
                continue
    if port is None:
        raise ValueError("No free Restore port (8530–8554).")
    log_dir = app / "output"
    log_dir.mkdir(exist_ok=True)
    # Query the selected audio Python; the tiny frozen launcher does not bundle psutil.
    created = subprocess.check_output(
        [
            str(python),
            "-c",
            "import psutil,sys;print(psutil.Process(int(sys.argv[1])).create_time())",
            str(args.desktop_owner or os.getpid()),
        ],
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    ).strip()
    command = [
        str(python),
        str(app / "restore.py"),
        "--port",
        str(port),
        "--no-browser",
        "--owner-pid",
        str(args.desktop_owner or os.getpid()),
        "--owner-created",
        created,
    ]
    detached = False
    if args.desktop_owner:
        command.append("--finish-on-close")
    with (log_dir / "launcher.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=app,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            for _ in range(80):
                if process.poll() is not None:
                    raise ValueError(
                        "Restore stopped during startup. See output/launcher.log."
                    )
                if healthy(port):
                    break
                time.sleep(0.25)
            else:
                raise ValueError("Restore startup timed out. See output/launcher.log.")
            url = f"http://127.0.0.1:{port}"
            if args.desktop_owner:
                announce(port)
                detached = True
                return 0
            print(
                f"Restore is ready at {url}\nKeep this window open. Closing it stops Restore.",
                flush=True,
            )
            if not args.no_browser:
                webbrowser.open(url)
            process.wait()
            return process.returncode
        except KeyboardInterrupt:
            return 0
        finally:
            if not detached and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f"Restore could not start: {exc}", flush=True)
        if getattr(sys, "frozen", False):
            input("Press Enter to close.")
        raise SystemExit(1)
