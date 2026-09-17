# Local vision inference

Ollama runs the model on this Mac. This is real extraction, not fixture mode.
The Gemini configuration remains available; switching providers never silently
sends a local document to Google.

## Installed on this machine

- Official Ollama 0.34.1 CLI/runtime: `.tools/ollama-runtime/` (ignored).
- Qwen3-VL 4B Instruct model: `data/ollama/models/` (ignored; approximately 3.3 GB per variant).
- Runtime is bound to `127.0.0.1:11434`, with `OLLAMA_NO_CLOUD=1`.
- Ollama also creates its normal local identity file under `~/.ollama`; it is
  outside this repository. No Ollama account or cloud sign-in was used.

## Start locally

Terminal one:

```sh
.venv/bin/python scripts/local_model.py
```

Terminal two, after saving these values in `.env`:

```dotenv
PROVIDER=ollama
OLLAMA_MODEL=qwen3-vl:4b-instruct
OLLAMA_TIMEOUT_SECONDS=240
```

```sh
.venv/bin/python scripts/dev.py
```

If port 11434 is already serving Ollama, do not start another instance. Keep cloud
features disabled. On another machine, install from [Ollama](https://ollama.com/download)
and run its local server, then `ollama pull qwen3-vl:4b-instruct`. The project wrapper expects
the runtime at the project-local path; an existing system installation can instead
be started with equivalent environment variables.

Upload actual files with **Choose a document**. The three fixture buttons still
skip model inference and remain explicitly labeled. The local model must not
calculate or repair printed amounts. Python independently verifies its output.

## Testing and limits

```sh
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_live.py output/pdf/*.pdf --provider ollama \
  --output data/evaluations/local-results.json
.venv/bin/python scripts/check_local_workflow.py
```

The default tests never contact Ollama or Gemini. The explicit evaluation command
uses the local runtime. Local requests have a bounded timeout and are not blindly
retried. There is no API fee, but memory, electricity and hardware costs remain.
Do not claim a zero operating cost or calibrated confidence. Start with one to
three pages, close memory-heavy apps, and measure your actual documents before
promising performance. The 20-page upload limit is not a local-model quality guarantee.

Gemini can be selected again with `PROVIDER=gemini` and an app restart. Jobs retain
their uploaded provider even when the active workspace changes. Keep both runtimes
available until old queued jobs finish, or allow unavailable jobs to fail visibly.

## Measured extraction results — 2026-09-17

Apple M4, 16 GB RAM; Ollama 0.34.1; `qwen3-vl:4b-instruct`; 8,192-token context;
temperature 0; up to 4,096 generated tokens. Ollama reported approximately 4.2 GB
loaded, using the GPU. This is not the machine's total memory consumption.

| Synthetic source | Actual route | Key result | Direct extraction time |
| --- | --- | --- | --- |
| Northline | Auto-approved | USD 1325.00, all 3 lines | 43.225s |
| Alder raster-only, two pages | Human review | All 6 lines; printed 1850.00, calculated 1800.00, variance +50.00 | 59.175s |
| Meridian | Human review | Date null; total 810.00 reconciles | 46.315s |

These are three known acceptance cases, not a held-out accuracy benchmark or a
latency SLA. The 30-second target is not met locally in these runs. For a 60-second
Loom, prepare completed runs and label any cut that skips inference time.

The default `qwen3-vl:4b` tag returned an empty final answer in two preliminary
checks; those responses were rejected. The explicit Instruct variant plus a
schema-bearing prompt resolved this. Both downloaded variants currently occupy
approximately 6.1 GB combined. No output was substituted from a fixture.

The separate HTTP acceptance run also passed all three cases through authenticated
upload, idempotent submission, the real queue/worker, persistence, private source
preview and audit endpoints. Measured worker times: 32.218s, 46.305s and 38.305s.
Results are saved locally in `data/evaluations/local-workflow.json`.

The browser displayed the successful Northline record, original source, passed
checks, local model name and real token telemetry. A fresh automated browser file
chooser attempt was interrupted by the browser-control session resetting; the
equivalent multipart upload path was verified through the API, not claimed as a
completed browser-upload test.

The Meridian result was subsequently used for an explicitly labeled synthetic
review simulation: the operator supplied a date, approval persisted, the original
null remained immutable, the audit recorded before/after, and a repeated decision
returned HTTP 409. Alder remains in the review queue for the Loom discrepancy demo.
