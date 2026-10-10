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
