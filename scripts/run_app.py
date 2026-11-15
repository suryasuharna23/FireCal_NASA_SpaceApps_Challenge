"""Launch the real-data API and website together on Linux and macOS."""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reachable(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def occupied(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open a browser (headless use)."
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Install Node.js 22.19+ first")
    version = subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
    if tuple(int(part) for part in version.split(".")[:2]) < (22, 19):
        raise RuntimeError("Node.js 22.19+ is required")
    vite = ROOT / "web/node_modules/vite/bin/vite.js"
    if not vite.is_file():
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("npm is required for the initial frontend install")
        subprocess.run(
            [
                npm,
                "exec",
                "--yes",
                "--package=pnpm@10.33.2",
                "--",
                "pnpm",
                "--dir",
                "web",
                "install",
                "--frozen-lockfile",
            ],
            check=True,
        )
    logs = ROOT / "data/live"
    logs.mkdir(parents=True, exist_ok=True)
    children = []

    def start(command, cwd, name):
        with (
            (logs / f"{name}.stdout.log").open("w") as out,
            (logs / f"{name}.stderr.log").open("w") as err,
        ):
            options = (
                {"start_new_session": True}
                if os.name != "nt"
                else {
                    "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
                }
            )
            process = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err, **options)
        children.append(process)

    try:
        for port, url, command, cwd, name in (
            (
                8000,
                "http://127.0.0.1:8000/health",
                [sys.executable, "-m", "firecal.cli", "serve"],
                ROOT,
                "api",
            ),
            (
                5173,
                "http://127.0.0.1:5173",
                [node, str(vite), "--host", "127.0.0.1"],
                ROOT / "web",
                "web",
            ),
        ):
            if not reachable(url):
                if occupied(port):
                    raise RuntimeError(f"Port {port} is occupied by another program")
                start(command, cwd, name)
        deadline = time.monotonic() + 180
        while not (
            reachable("http://127.0.0.1:8000/health") and reachable("http://127.0.0.1:5173")
        ):
            if time.monotonic() > deadline or any(p.poll() is not None for p in children):
                raise RuntimeError("Startup failed; check the API/web logs under data/live")
            time.sleep(1)
        with urllib.request.urlopen("http://127.0.0.1:8000/meta", timeout=10) as response:
            meta = json.load(response)
        if meta.get("status") != "ok" or (meta.get("coverage") or {}).get("country") != "Indonesia":
            raise RuntimeError("The API is not serving the expected real Indonesia data")
        worldwide = meta.get("global") or {}
        if worldwide.get("status") != "ok":
            raise RuntimeError("Worldwide data is unavailable; stop an older FireCal API and retry")
        print("FireCal: http://localhost:5173", flush=True)
        live_status = (meta.get("live") or {}).get("status")
        if live_status == "missing_key":
            update_note = "Set FIRMS_MAP_KEY to enable NASA catch-up."
        elif live_status == "failed":
            update_note = "NASA catch-up failed; the saved observations remain available."
        else:
            update_note = "NASA catch-up is managed by the backend."
        print(f"Real observations through {meta.get('last_acq_date')}. {update_note}")
        print(
            f"Worldwide: {worldwide['start_date']} through {worldwide['last_acq_date']}. "
            "Choose Worldwide under the globe."
        )
        if not args.no_browser:
            webbrowser.open("http://localhost:5173", new=2)
        if not children:
            print("Both services were already running.")
            return
        print("Keep this terminal open. Press Ctrl+C to stop services started here.", flush=True)
        while True:
            if any(p.poll() is not None for p in children):
                raise RuntimeError("A service stopped; check data/live logs")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in children:
            if os.name == "nt":
                if process.poll() is None:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    continue
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"FireCal: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
