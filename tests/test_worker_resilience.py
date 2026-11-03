import logging
from io import StringIO

import pytest

from app import retention, worker


@pytest.mark.parametrize("cleanup", ["expire_guest_uploads", "expire_sources"])
def test_cleanup_failures_do_not_leak_through_alternate_log_handlers(monkeypatch, cleanup):
    output = StringIO()
    handler = logging.StreamHandler(output)
    monkeypatch.setattr(worker.logger, "handlers", [handler])
    monkeypatch.setattr(worker.logger, "propagate", False)
    monkeypatch.setattr(worker, "configure_logging", lambda: None)
    monkeypatch.setattr(worker.time, "monotonic", lambda: 10_000)
    monkeypatch.setattr(retention, "expire_guest_uploads", lambda: 0)
    monkeypatch.setattr(retention, "expire_sources", lambda **kwargs: [])

    def fail(*args, **kwargs):
        raise RuntimeError("private invoice and database details")

    def stop_after_cleanup():
        raise KeyboardInterrupt

    monkeypatch.setattr(retention, cleanup, fail)
    monkeypatch.setattr(worker, "run_once", stop_after_cleanup)
    with pytest.raises(KeyboardInterrupt):
        worker.main()
    assert output.getvalue() == "source_retention_failed\n"
