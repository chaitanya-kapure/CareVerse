#!/usr/bin/env python
"""Start the CAREVERSE API in development.

Kept as a script rather than an npm task because the server is Python, and
resolving the virtualenv differs between Windows and Unix. Running
`python dev.py` works from either platform and from an activated venv.

    python dev.py            # normal
    python dev.py --port 8001
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent

# Windows layout differs from the POSIX one.
VENV_PYTHON = SERVER_DIR / ".venv" / (
    "Scripts/python.exe" if os.name == "nt" else "bin/python"
)


def resolve_python() -> str:
    """Prefer the project venv; fall back to whatever python is on PATH."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    if sys.prefix != sys.base_prefix:
        return sys.executable  # already inside an activated venv
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CAREVERSE API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="disable auto-reload")
    args = parser.parse_args()

    python = resolve_python()
    print(f"CAREVERSE API -> http://{args.host}:{args.port}  (docs at /docs)")
    print(f"Interpreter    -> {python}")

    command = [
        python,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if not args.no_reload:
        command.append("--reload")

    # cwd matters: the app resolves .env and storage/ relative to server/.
    return subprocess.call(command, cwd=str(SERVER_DIR))


if __name__ == "__main__":
    raise SystemExit(main())
