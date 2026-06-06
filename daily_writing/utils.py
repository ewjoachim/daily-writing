import calendar
import datetime
import functools
import itertools
import pathlib
import random
import string
from collections.abc import Callable, Iterable
from typing import Any

import yarl


@functools.cache
def excerpt(text: str, max_length: int = 200) -> str:
    words = text.split()

    length = 0
    take_first = 0
    suffix = "…"
    for i, word in enumerate(words):
        length += len(word) + 1
        if length + len(suffix) >= max_length:
            break
        take_first = i
    else:
        suffix = ""
    return " ".join(words[:take_first]) + suffix


def color_gradient(colors: list[str]) -> list[tuple[str, float]]:
    if len(colors) == 1:
        return [(colors[0], 0)]
    colors_levels: list[tuple[str, float]] = []
    level = 0
    increment = 1 / (len(colors) - 1)
    for color in colors:
        colors_levels.append((color, level))
        level += increment

    return colors_levels


def get_prev[T](obj: T, iterable: Iterable[T]) -> T | None:
    for prev, current in itertools.pairwise(iterable):
        if current is obj:
            return prev
    return None


def get_next[T](obj: T, iterable: Iterable[T]) -> T | None:
    for current, next_item in itertools.pairwise(iterable):
        if current is obj:
            return next_item
    return None


def get_repository_url_for_file(
    repository_url: str, repository_file_url_prefix: str, file: pathlib.Path
) -> str:
    return str(yarl.URL(repository_url) / repository_file_url_prefix / str(file))


def cache_bust():
    return "".join(random.choices(string.digits + string.ascii_letters, k=12))  # noqa: S311


def date_grouper[T](
    index: int, element: T, *, key: Callable[[T], datetime.date]
) -> tuple[int, int, int, int]:
    """
    Take an object from which a date can be extracted, and its index in an iterable, and
    return a tuple that will have the same value for consecutive days in the same week.
    """
    date = key(element)
    _, week, _ = date.isocalendar()
    return (
        date.year,
        date.month,
        week,
        (date - datetime.date(2000, 1, 1)).days - index,
    )


def first_weekday(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[0]


def same_month(*dates: datetime.date) -> bool:
    return len({(date.year, date.month) for date in dates}) == 1


def deep_merge(d1: dict[str, Any], d2: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries. d2 values take precedence over d1."""
    merged = dict(d1)
    for key, value in d2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)  # pyright: ignore[reportUnknownArgumentType]
        else:
            merged[key] = value
    return merged
