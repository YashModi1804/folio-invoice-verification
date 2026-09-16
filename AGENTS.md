# Engineering rules

Read SRS.md and BUILD_PLAN.md before changing behavior.

- Product goal: a credible agency sales demo of auditable invoice processing.
- Python domain logic lives in `app/domain`; routes only orchestrate.
- Use Decimal for financial values. Missing values are never implicit zeroes.
- Never trust model confidence as calibrated probability or proof of correctness.
- Preserve original extraction and append reviewer decisions.
- Fixture mode must be visibly labeled. Never present fixtures as live inference.
- No live provider calls in the default test suite.
- Never commit secrets, uploaded documents, local databases, or dependencies.
- Tests: `.venv/bin/python -m pytest`; lint: `.venv/bin/ruff check .`.
- Format: `.venv/bin/ruff format .`; frontend: `pnpm --dir web build`.
- Keep UI copy focused on reviewer decisions; technical details belong in the trace.
- Commit coherent, verified changes according to BUILD_PLAN.md.
