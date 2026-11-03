import json
import os
import signal
import subprocess
import sys
from io import BytesIO
from threading import BoundedSemaphore

import pymupdf
import pytest
from PIL import Image

from app import parser, parser_child
from app.config import settings
from app.samples import sample_pdf
from app.storage import DocumentError, inspect, page_texts, render


def test_real_pdf_inspection_text_and_selected_render():
    data = sample_pdf("helixpoint")
    assert inspect(data, "invoice.pdf") == ("application/pdf", 2)
    texts = page_texts(data, "application/pdf")
    assert len(texts) == 2
    assert "HELIXPOINT" in "".join(texts).upper()
    pages = render(data, "application/pdf", (2,))
    assert len(pages) == 1
    with Image.open(BytesIO(pages[0])) as image:
        assert image.format == "PNG"
        assert 0 < image.width * image.height < 25_000_000


def test_real_image_is_inspected_and_resized():
    output = BytesIO()
    Image.new("RGB", (3000, 1000), "white").save(output, "PNG")
    data = output.getvalue()
    assert inspect(data, "image.png") == ("image/png", 1)
    assert page_texts(data, "image/png") == [""]
    with Image.open(BytesIO(render(data, "image/png")[0])) as image:
        assert image.size == (2400, 800)


def test_image_frames_and_pdf_dimensions_are_bounded():
    output = BytesIO()
    Image.new("RGB", (10, 10), "white").save(
        output, "WEBP", save_all=True, append_images=[Image.new("RGB", (10, 10), "black")]
    )
    with pytest.raises(DocumentError, match="ANIMATED_IMAGE_UNSUPPORTED"):
        inspect(output.getvalue(), "animated.webp")
    with pymupdf.open() as doc:
        doc.new_page(width=6000, height=100)
        data = doc.tobytes()
    with pytest.raises(DocumentError, match="PAGE_DIMENSIONS_LIMIT"):
        render(data, "application/pdf")


def test_invalid_pages_and_corrupt_source_are_safe():
    with pytest.raises(DocumentError, match="PAGE_NOT_FOUND"):
        render(sample_pdf("clean"), "application/pdf", (3,))
    with pytest.raises(DocumentError, match="CORRUPT_DOCUMENT"):
        inspect(b"%PDF-private document text", "invoice.pdf")


def fake_process(monkeypatch, output, *, returncode=0, timeout=False):
    captured = {}

    class Child:
        def __init__(self, command, **kwargs):
            self.returncode = None
            self.calls = []
            captured.update(command=command, kwargs=kwargs, child=self)
            kwargs["stdout"].write(output)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def communicate(self, data=None, timeout=None):
            self.calls.append((data is not None, timeout))
            if timeout is not None and fail_timeout:
                raise subprocess.TimeoutExpired("parser", timeout)
            if self.returncode is None:
                self.returncode = returncode

        def poll(self):
            return self.returncode

        def kill(self):
            self.calls.append("kill")
            self.returncode = -signal.SIGKILL

    fail_timeout = timeout
    monkeypatch.setattr(parser.subprocess, "Popen", Child)
    return captured


def test_child_receives_no_parent_credentials_or_shell(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "private-test-secret")
    captured = fake_process(
        monkeypatch,
        b'{"operation":"inspect","media_type":"application/pdf","pages":1}\n',
    )
    assert inspect(b"%PDF-test", "invoice.pdf") == ("application/pdf", 1)
    assert captured["command"][:3] == [sys.executable, "-I", "-B"]
    assert captured["kwargs"]["env"] == {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    assert "shell" not in captured["kwargs"]
    assert captured["kwargs"]["close_fds"] is True
    assert captured["kwargs"]["stdout"].closed


def test_timeout_kills_reaps_and_releases_slot(monkeypatch):
    captured = fake_process(monkeypatch, b"", timeout=True)
    with pytest.raises(DocumentError, match="PARSER_TIMEOUT"):
        inspect(b"%PDF-test", "invoice.pdf")
    assert "kill" in captured["child"].calls
    assert captured["child"].calls[-1] == (False, None)
    assert captured["kwargs"]["stdout"].closed
    assert parser._slot.acquire(blocking=False)
    parser._slot.release()


def test_real_timeout_leaves_no_running_child(tmp_path, monkeypatch):
    script = tmp_path / "slow_parser.py"
    script.write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(parser, "_child", script)
    monkeypatch.setattr(settings, "parser_timeout_seconds", 1)
    original, children = parser.subprocess.Popen, []

    def spawn(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(parser.subprocess, "Popen", spawn)
    with pytest.raises(DocumentError, match="PARSER_TIMEOUT"):
        inspect(b"%PDF-test", "invoice.pdf")
    assert len(children) == 1
    assert children[0].returncode == -signal.SIGKILL
    with pytest.raises(ProcessLookupError):
        os.kill(children[0].pid, 0)


@pytest.mark.parametrize(
    ("returncode", "code"),
    [(-signal.SIGSEGV, "PARSER_FAILED"), (-signal.SIGXCPU, "PARSER_RESOURCE_LIMIT")],
)
def test_crashes_and_resource_limits_are_redacted(monkeypatch, returncode, code):
    captured = fake_process(monkeypatch, b"private native failure", returncode=returncode)
    with pytest.raises(DocumentError, match=f"^{code}$"):
        inspect(b"%PDF-test", "invoice.pdf")
    assert captured["kwargs"]["stderr"] == subprocess.DEVNULL
    assert captured["kwargs"]["stdout"].closed


@pytest.mark.parametrize(
    ("operation", "output"),
    [
        ("inspect", b"private native failure"),
        ("inspect", b'{"error":"private native failure"}\n'),
        (
            "inspect",
            b'{"operation":"inspect","media_type":"application/pdf","pages":true}\n',
        ),
        ("render", b'{"operation":"render","lengths":[10]}\nshort'),
        ("render", b'{"operation":"render","lengths":[8]}\n\x89PNG\r\n\x1a\n'),
        ("text", b'{"operation":"text"}\n[42]'),
    ],
)
def test_malformed_child_output_is_rejected(monkeypatch, operation, output):
    fake_process(monkeypatch, output)
    with pytest.raises(DocumentError, match="^PARSER_FAILED$"):
        parser.parse(b"%PDF-test", operation, media_type="application/pdf")


def test_parent_bounds_output_and_busy_admission(monkeypatch):
    monkeypatch.setattr(settings, "parser_max_output_bytes", 100)
    fake_process(monkeypatch, b"x" * (parser.HEADER_LIMIT + 101))
    with pytest.raises(DocumentError, match="PARSER_OUTPUT_LIMIT"):
        inspect(b"%PDF-test", "invoice.pdf")
    slot = BoundedSemaphore(1)
    monkeypatch.setattr(parser, "_slot", slot)
    slot.acquire()
    try:
        with pytest.raises(DocumentError, match="PARSER_BUSY"):
            inspect(b"%PDF-test", "invoice.pdf")
    finally:
        slot.release()


def test_linux_enforces_memory_limit_and_macos_keeps_explicit_fallback(monkeypatch):
    calls = []
    monkeypatch.setattr(parser_child.resource, "setrlimit", lambda *args: calls.append(args))
    monkeypatch.setattr(parser_child.sys, "platform", "linux")
    parser_child.set_limits(10, 256, 1024)
    assert (parser_child.resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2) in calls
    assert (parser_child.resource.RLIMIT_CPU, (10, 11)) in calls
    assert (parser_child.resource.RLIMIT_CORE, (0, 0)) in calls
    calls.clear()
    monkeypatch.setattr(parser_child.sys, "platform", "darwin")
    parser_child.set_limits(10, 256, 1024)
    assert all(kind != parser_child.resource.RLIMIT_AS for kind, _ in calls)
    assert len(calls) == 3


def test_text_protocol_has_total_size_bound(monkeypatch):
    fake_process(
        monkeypatch,
        b'{"operation":"text"}\n' + json.dumps(["x" * (parser.TEXT_LIMIT + 1)]).encode(),
    )
    with pytest.raises(DocumentError, match="PARSER_FAILED"):
        page_texts(b"%PDF-test", "application/pdf")
