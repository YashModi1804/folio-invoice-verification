def test_security_headers_cover_public_and_protected_routes(client):
    for path in ("/", "/health/live", "/api/v1/jobs"):
        response = client.get(path)
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "camera=()" in response.headers["permissions-policy"]
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert response.headers["x-correlation-id"]


def test_early_rejection_has_security_headers(client):
    response = client.post(
        "/api/v1/documents",
        headers={"Content-Length": "999999999"},
    )
    assert response.status_code == 413
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


def test_non_ascii_and_oversized_bearer_tokens_return_401(client):
    for token in (b"caf\xe9", b"x" * 513):
        response = client.get("/api/v1/jobs", headers={b"Authorization": b"Bearer " + token})
        assert response.status_code == 401
        assert response.headers["x-frame-options"] == "DENY"


def test_body_limit_counts_received_bytes_not_just_content_length(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_request_body_bytes", 1024)
    for headers in ({}, {"Content-Length": "1"}):
        response = client.post(
            "/api/v1/review-tasks/missing/decision",
            content=iter([b'{"note":"', b"x" * 2048, b'"}']),
            headers={"Content-Type": "application/json", **headers},
        )
        assert response.status_code == 413
        assert response.json()["detail"] == "REQUEST_BODY_LIMIT"
        assert response.headers["cache-control"] == "no-store"


def test_oversized_multipart_stream_is_rejected_before_intake(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_file_bytes", 1)
    boundary = "folio-test"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="invoice.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + b"x" * 70000
        + f"\r\n--{boundary}--\r\n".encode()
    )
    response = client.post(
        "/api/v1/documents",
        content=body,
        headers={
            "Content-Length": "1",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Idempotency-Key": "oversized-stream",
        },
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "FILE_SIZE_LIMIT"


def test_invalid_content_length_is_a_safe_client_error(client):
    for length in ("no", "9" * 5000):
        response = client.post("/api/v1/guest-sessions", headers={"Content-Length": length})
        assert response.status_code == 400
        assert response.headers["x-correlation-id"]


def test_unexpected_failure_is_redacted_and_keeps_protective_headers(client, monkeypatch, caplog):
    from app import api

    assert client.post("/api/v1/samples/clean").status_code == 202

    def fail(_job):
        raise RuntimeError("private-database-password")

    monkeypatch.setattr(api, "serialize", fail)
    response = client.get("/api/v1/jobs")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-correlation-id"] == response.json()["correlation_id"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "private-database-password" not in response.text + caplog.text


def test_launcher_readiness_has_scoped_cors_and_no_internal_details(client):
    from app import worker

    starting = client.get("/health/launch")
    assert starting.status_code == 503
    assert starting.json() == {"status": "starting"}
    assert starting.headers["access-control-allow-origin"] == "https://yashmodi1804.github.io"
    assert starting.headers["cache-control"] == "no-store"
    worker.run_once()
    ready = client.get("/health/launch")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert "access-control-allow-credentials" not in ready.headers
    assert "access-control-allow-origin" not in client.get("/api/v1/jobs").headers
