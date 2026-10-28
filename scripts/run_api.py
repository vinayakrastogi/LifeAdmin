"""Start LifeAdmin's API and its fixed ngrok tunnel; Ctrl+C stops both."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def public_url(domain: str) -> str:
    parsed = urlparse(domain if "://" in domain else "https://" + domain)
    hostname = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.netloc != hostname
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment
            or len(hostname) > 253
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", hostname)
            or "." not in hostname):
        raise ValueError("NGROK_DOMAIN must be your assigned domain or its HTTPS URL, without a port or path.")
    return "https://" + hostname


def spawn(command: list[str], env: dict, label: str, secrets: list[str]) -> subprocess.Popen:
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

    def stream():
        for line in process.stdout:
            for value in secrets:
                if value:
                    line = line.replace(value, "[redacted]")
            print(f"[{label}] {line.rstrip()}", flush=True)

    threading.Thread(target=stream, daemon=True).start()
    return process


def wait_for_health(url: str, children: list[subprocess.Popen], timeout: int = 45) -> None:
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=3, trust_env=False, headers={"ngrok-skip-browser-warning": "1"}) as client:
        while time.monotonic() < deadline:
            if any(child.poll() is not None for child in children):
                raise RuntimeError("A service exited during startup. Check the messages above.")
            try:
                response = client.get(url)
                if response.status_code == 200 and response.json().get("service") == "lifeadmin":
                    return
            except (httpx.HTTPError, ValueError, AttributeError):
                pass
            time.sleep(0.5)
    raise RuntimeError(f"Could not reach {url}. Check the ngrok account/domain and internet connection.")


def stop(children: list[subprocess.Popen]) -> None:
    for process in reversed(children):
        if process.poll() is None:
            process.terminate()
    for process in reversed(children):
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main() -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-only", action="store_true", help="Run the API without a public tunnel.")
    parser.add_argument("--port", type=int, default=8001, help="Local API port (default: 8001).")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    env = os.environ.copy()
    key = env.get("LIFEADMIN_API_KEY", "")
    token = env.get("NGROK_AUTHTOKEN", "")
    if len(key) < 32:
        parser.error("Set LIFEADMIN_API_KEY in LifeAdmin/.env to the shared key (at least 32 characters).")
    tunnel_url = None
    binary = None
    if not args.local_only:
        if not token or not env.get("NGROK_DOMAIN"):
            parser.error("Set NGROK_AUTHTOKEN and NGROK_DOMAIN in LifeAdmin/.env, or use --local-only.")
        try:
            tunnel_url = public_url(env["NGROK_DOMAIN"])
        except ValueError as exc:
            parser.error(str(exc))
        binary = shutil.which("ngrok")
        if binary is None:
            parser.error("Install the ngrok CLI from https://ngrok.com/download, then run this command again.")

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    children = []
    try:
        with tempfile.TemporaryDirectory(prefix="lifeadmin-ngrok-") as temporary:
            # A private temporary config avoids putting the authtoken in command-line arguments.
            config = Path(temporary) / "ngrok.yml"
            config.write_text(json.dumps({"version": "3", "agent": {"authtoken": token}}))
            config.chmod(0o600)
            api_env = {k: v for k, v in env.items() if k != "NGROK_AUTHTOKEN"}
            print(f"Starting LifeAdmin API on port {args.port}...", flush=True)
            children.append(spawn([sys.executable, "-m", "uvicorn", "lifeadmin.api:app", "--host", "0.0.0.0",
                                   "--port", str(args.port)], api_env, "api", [token, key]))
            wait_for_health(f"http://127.0.0.1:{args.port}/health", children, timeout=20)
            if tunnel_url:
                print(f"Starting fixed tunnel: {tunnel_url}", flush=True)
                children.append(spawn([binary, "http", f"http://127.0.0.1:{args.port}", "--url", tunnel_url,
                                       "--config", str(config), "--log", "stdout", "--log-format", "json"],
                                      api_env, "ngrok", [token, key]))
                wait_for_health(tunnel_url + "/health", children)
                print(f"Public API ready: {tunnel_url}\nAPI documentation: {tunnel_url}/docs", flush=True)
            else:
                print(f"Local API ready: http://localhost:{args.port}", flush=True)
            print("Press Ctrl+C to stop the API and tunnel.", flush=True)
            while all(child.poll() is None for child in children):
                time.sleep(0.5)
            raise RuntimeError("A service stopped; shutting down the remaining processes.")
    except KeyboardInterrupt:
        return 0
    except (OSError, RuntimeError) as exc:
        message = str(exc)
        for secret in (token, key):
            if secret:
                message = message.replace(secret, "[redacted]")
        print(message, file=sys.stderr, flush=True)
        return 1
    finally:
        stop(children)
        print("LifeAdmin API and tunnel stopped.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
