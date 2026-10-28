import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from scripts.run_api import public_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("domain", ["example.ngrok-free.dev", "https://example.ngrok-free.dev/"])
def test_assigned_domain_accepts_hostname_or_https(domain):
    assert public_url(domain) == "https://example.ngrok-free.dev"


@pytest.mark.parametrize("domain", ["http://example.com", "https://user:password@example.com",
                                    "example.com/path", "example.com:8001", "example.com?q=x", "localhost"])
def test_domain_does_not_accept_other_protocols_credentials_ports_or_paths(domain):
    with pytest.raises(ValueError):
        public_url(domain)


def test_local_launcher_starts_and_terminates_its_api(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, LIFEADMIN_DB=str(tmp_path / "launcher.db"),
               LIFEADMIN_API_KEY="launcher-test-" + "x" * 32, NGROK_AUTHTOKEN="fake-test-token")
    process = subprocess.Popen([sys.executable, "scripts/run_api.py", "--local-only", "--port", str(port)],
                               cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        with httpx.Client(timeout=.5, trust_env=False) as client:
            for _ in range(80):
                assert process.poll() is None
                try:
                    if client.get(f"http://127.0.0.1:{port}/health").json().get("service") == "lifeadmin":
                        break
                except (httpx.HTTPError, ValueError):
                    pass
                time.sleep(.1)
            else:
                pytest.fail("Local API did not start")
        process.terminate()
        output = process.communicate(timeout=10)[0]
        assert process.returncode == 0, output
        assert "fake-test-token" not in output
        assert env["LIFEADMIN_API_KEY"] not in output
        for _ in range(30):
            try:
                httpx.get(f"http://127.0.0.1:{port}/health", timeout=.2)
            except httpx.ConnectError:
                break
            time.sleep(.1)
        else:
            pytest.fail("API was left running after the launcher stopped")
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
