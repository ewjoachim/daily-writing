import datetime

import babel
import pytest

from daily_writing import i18n


def test_locale_from_string():
    locale = i18n.Locale.from_string("fr-fr")
    assert isinstance(locale.locale, babel.Locale)
    assert locale.locale.language == "fr"
    assert locale.locale.territory == "FR"


def test_locale_from_string__invalid():
    with pytest.raises(i18n.LocaleError):
        i18n.Locale.from_string("xx-xx")


def test_locale_default():
    assert isinstance(i18n.Locale.default().locale, babel.Locale)


def test_full_date():
    result = i18n.full_date(
        dates=[datetime.date(2024, 10, 1), datetime.date(2024, 10, 2)],
        locale=i18n.Locale.from_string("en-us"),
    )
    assert result == "October 1, 2024, October 2, 2024"


def test_month_date():
    result = i18n.month_date(
        year=2024, month=10, locale=i18n.Locale.from_string("en-us")
    )
    assert result == "October 2024"


@pytest.mark.parametrize(
    ("locale_str", "expected"),
    [
        ("fr-fr", "fr-FR"),
        ("fr", "fr"),
    ],
)
def test_get_bcp47(locale_str, expected):
    assert i18n.get_bcp47(i18n.Locale.from_string(locale_str)) == expected
