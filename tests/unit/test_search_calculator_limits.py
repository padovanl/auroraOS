"""Spotlight's calculator runs in the shell at every key: nothing may hang it."""

import time

import gi

gi.require_version("Gtk", "4.0")
from aurora.shell.search import calculate, format_number, search_calculator  # noqa: E402


def test_huge_results_are_refused_quickly():
    start = time.monotonic()
    for expr in ("((999^999)^999)^999", "factorial(99999999)", "(999^999)^999",
                 "1e308*10", "(9^999)*(9^999)*(9^999)*(9^999)*(9^999)"):
        assert calculate(expr) is None, expr
    assert time.monotonic() - start < 2


def test_big_numbers_read_in_scientific_notation():
    assert format_number(9 ** 999) == "1.94207916858e+953"
    assert format_number(10 ** 15) == "1e+15"
    assert format_number(123456) == "123456"
    assert search_calculator("9^999")[0].title == "= 1.94207916858e+953"
    assert calculate("2+2") == 4 and calculate("1/3") == 0.3333333333
