import pytest

from aurora.shell import search


@pytest.mark.parametrize("expr, expected", [
    ("2+2", 4),
    ("12*(3+4)", 84),
    ("2^10", 1024),
    ("10/4", 2.5),
    ("sqrt(16)", 4),
    ("=7-10", -3),
    ("3×4", 12),
    ("1,5*2", 3),
])
def test_calculator_evaluates(expr, expected):
    assert search.calculate(expr) == expected


@pytest.mark.parametrize("expr", [
    "firefox", "", "hello world", "__import__('os')", "2**100000", "1/0", "open('x')",
])
def test_calculator_rejects_unsafe_or_non_math(expr):
    assert search.calculate(expr) is None


def test_command_prefix_only_offers_running_it():
    results = search.search("> ls -la", lambda page: None)
    assert len(results) == 1
    assert "ls -la" in results[0].title


def test_web_search_is_always_last():
    results = search.search("something unlikely xyz", lambda page: None)
    assert results[-1].subtitle == "duckduckgo.com"


def test_settings_pages_are_found():
    results = search.search_settings("wifi", lambda page: None)
    assert any("Network" in r.title for r in results)
