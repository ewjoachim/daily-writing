import datetime
from typing import Self

import babel
import babel.dates
import pydantic
from pydantic import dataclasses as pdataclasses


class LocaleError(Exception):
    pass


@pdataclasses.dataclass(config=pydantic.ConfigDict(arbitrary_types_allowed=True))
class Locale:
    locale: babel.Locale

    @classmethod
    def from_string(cls, locale_str: str) -> Self:
        try:
            return cls(locale=babel.Locale.parse(locale_str, sep="-"))
        except babel.UnknownLocaleError as exc:
            raise LocaleError(str(exc)) from exc


def full_date(dates: list[datetime.date], locale: Locale | None) -> str:
    return ", ".join(
        babel.dates.format_date(
            date=date, format="long", locale=locale.locale if locale else None
        )
        for date in dates
    )


def month_date(year: int, month: int, locale: Locale | None) -> str:
    return babel.dates.format_skeleton(
        skeleton="yyyyMMMM",
        datetime=datetime.date(year, month, 1),
        locale=locale.locale if locale else None,
    ).capitalize()


def get_bcp47(locale: Locale) -> str:
    if locale.locale.territory:
        return f"{locale.locale.language}-{locale.locale.territory}"
    return locale.locale.language
