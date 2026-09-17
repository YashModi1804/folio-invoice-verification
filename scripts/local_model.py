"""Start the project-local Ollama runtime without exposing a network service."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    binary = ROOT / ".tools/ollama-runtime/ollama"
    if not binary.is_file():
        raise SystemExit("Install Ollama first; see docs/LOCAL_INFERENCE.md.")
    environment = os.environ | {
        "OLLAMA_HOST": "127.0.0.1:11434",
        "OLLAMA_MODELS": str(ROOT / "data/ollama/models"),
        "OLLAMA_NO_CLOUD": "1",
        "OLLAMA_NUM_PARALLEL": "1",
    }
    raise SystemExit(subprocess.call([str(binary), "serve"], env=environment))


if __name__ == "__main__":
    main()
