import datetime
import pathlib

import pytest

from daily_writing import utils


def test_excerpt__short():
    # A text that fits gets no ellipsis (the last word is dropped by the loop).
    result = utils.excerpt("one two three")
    assert not result.endswith("…")
    assert result == "one two"


def test_excerpt__truncated():
    text = " ".join(f"word{i}" for i in range(100))
    result = utils.excerpt(text, max_length=30)

    assert result.endswith("…")
    assert len(result) < 40


@pytest.mark.parametrize(
    ("colors", "expected"),
    [
        (["#fff"], [("#fff", 0)]),
        (["#000", "#fff"], [("#000", 0.0), ("#fff", 1.0)]),
    ],
)
def test_color_gradient(colors, expected):
    assert utils.color_gradient(colors) == expected


@pytest.mark.parametrize(
    ("target", "expected"),
    [(1, 0), (0, None)],
)
def test_get_prev(target, expected):
    items = [object(), object(), object()]
    result = utils.get_prev(items[target], items)
    assert result is (None if expected is None else items[expected])


@pytest.mark.parametrize(
    ("target", "expected"),
    [(1, 2), (2, None)],
)
def test_get_next(target, expected):
    items = [object(), object(), object()]
    result = utils.get_next(items[target], items)
    assert result is (None if expected is None else items[expected])


def test_get_repository_url_for_file():
    result = utils.get_repository_url_for_file(
        repository_url="https://github.com/foo/bar",
        repository_file_url_prefix="blob/HEAD",
        file=pathlib.Path("2024/10/01-foo.md"),
    )
    assert result == "https://github.com/foo/bar/blob/HEAD/2024/10/01-foo.md"


def test_cache_bust():
    value = utils.cache_bust()
    assert len(value) == 12
    assert value.isalnum()
    assert value != utils.cache_bust()


@pytest.mark.parametrize(
    ("second_day", "expect_same_group"),
    [(2, True), (8, False)],
)
def test_date_grouper(second_day, expect_same_group):
    def key(d):
        return d

    first = utils.date_grouper(0, datetime.date(2024, 10, 1), key=key)
    second = utils.date_grouper(1, datetime.date(2024, 10, second_day), key=key)
    assert (first == second) is expect_same_group


def test_first_weekday():
    # 2024-10-01 is a Tuesday (Monday=0)
    assert utils.first_weekday(2024, 10) == 1


@pytest.mark.parametrize(
    ("dates", "expected"),
    [
        ((datetime.date(2024, 10, 1), datetime.date(2024, 10, 31)), True),
        ((datetime.date(2024, 10, 1), datetime.date(2024, 11, 1)), False),
    ],
)
def test_same_month(dates, expected):
    assert utils.same_month(*dates) is expected


def test_deep_merge__nested():
    d1 = {"a": {"x": 1, "y": 2}, "b": 3}
    d2 = {"a": {"y": 20, "z": 30}, "c": 4}

    assert utils.deep_merge(d1, d2) == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}


def test_deep_merge__does_not_mutate():
    d1 = {"a": {"x": 1}}
    utils.deep_merge(d1, {"a": {"y": 2}})
    assert d1 == {"a": {"x": 1}}
