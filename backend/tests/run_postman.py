"""Run Newman and shut down its disposable fixture server in the same process.

Example:
python -m backend.tests.run_postman --newman-cli ../.coursehub-tools/node_modules/newman/bin/newman.js --output docs/evidence/postman_events.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import threading
import time

import uvicorn

from backend.tests.postman_demo import make_demo_app


ROOT = Path(__file__).resolve().parents[2]
COLLECTION = ROOT / "postman/CourseHub_Enrollment_Events.postman_collection.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--newman-cli", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/evidence/postman_events.json"
    )
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    if not args.newman_cli.is_file():
        parser.error("--newman-cli must point to newman/bin/newman.js")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    server = uvicorn.Server(uvicorn.Config(
        make_demo_app(), host="127.0.0.1", port=args.port,
        reload=False, timeout_graceful_shutdown=5,
    ))
    # A worker thread installs no process signal handlers. Shutdown is requested
    # through should_exit and the lifespan cleanup is joined before returning.
    thread = threading.Thread(
        target=server.run, name="coursehub-postman-server", daemon=True,
    )
    thread.start()
    exit_code = 1
    try:
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive():
                raise RuntimeError("Postman fixture server exited during startup")
            if time.monotonic() >= deadline:
                raise RuntimeError("Postman fixture server did not start within 10s")
            time.sleep(0.1)

        completed = subprocess.run([
            "node", str(args.newman_cli.resolve()), "run", str(COLLECTION),
            "--env-var", f"base_url=http://127.0.0.1:{args.port}",
            "-r", "cli,json", "--reporter-json-export", str(args.output.resolve()),
        ], timeout=90, check=False)
        exit_code = completed.returncode
    except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
        print(f"Postman runner failed: {exc}", file=sys.stderr)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            print("Postman fixture server did not stop within 10s", file=sys.stderr)
            exit_code = 1
        lifespan = getattr(server, "lifespan", None)
        if getattr(lifespan, "shutdown_failed", False):
            print("Postman fixture cleanup failed", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
