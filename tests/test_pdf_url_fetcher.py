import pytest

from app.services.pdf_service import _safe_url_fetcher, render_pdf


def test_pdf_url_fetcher_allows_embedded_data():
    response = _safe_url_fetcher()("data:text/plain;base64,SGVsbG8=")
    try:
        assert response.read() == b"Hello"
    finally:
        response.close()


@pytest.mark.parametrize("url", ["file:///etc/passwd", "https://example.com/logo.png"])
def test_pdf_url_fetcher_rejects_external_resources(url):
    with pytest.raises(ValueError, match="disallowed protocol"):
        _safe_url_fetcher()(url)


def test_weasyprint_70_renders_pdf_with_restricted_fetcher():
    assert render_pdf("<h1>Phase 6</h1>").startswith(b"%PDF")
