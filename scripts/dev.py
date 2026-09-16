"""Start the migrated local API and worker together; Ctrl-C shuts down both."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    if not (ROOT / "web/dist/index.html").exists():
        raise SystemExit("Build the console first: pnpm --dir web install && pnpm --dir web build")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    children = []
    try:
        for args in (["-m", "app.worker"],
                     ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]):
            children.append(subprocess.Popen([sys.executable, *args]))
        print("Folio: http://127.0.0.1:8000 | local demo token: local-demo-only", flush=True)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        while all(process.poll() is None for process in children):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in children:
            process.terminate()
        for process in children:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
    if any(process.returncode not in (0, -15, -2) for process in children):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
