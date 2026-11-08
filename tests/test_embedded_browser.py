import pytest

from core.embedded_browser import normalize_browser_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("youtube.com", "https://youtube.com/"),
        ("https://www.youtube.com/watch?v=abc", "https://www.youtube.com/watch?v=abc"),
        ("http://localhost:5000/app", "http://localhost:5000/app"),
    ],
)
def test_normalize_browser_url_accepts_http_sites(raw, expected):
    assert normalize_browser_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "javascript:alert(1)",
        "file:///C:/Windows/win.ini",
        "data:text/html,hello",
        "https://user:password@example.com",
        "https://",
        "https://example.com/\nmalicious",
    ],
)
def test_normalize_browser_url_rejects_unsafe_or_invalid_input(raw):
    with pytest.raises(ValueError):
        normalize_browser_url(raw)
