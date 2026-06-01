import pytest

from mm_post_bot.i18n import CATALOG, SUPPORTED_LOCALES, normalize_locale, translate


def test_supported_locales_are_english_and_russian():
    assert frozenset({"en", "ru"}) == SUPPORTED_LOCALES


def test_normalize_locale_accepts_supported_values():
    assert normalize_locale("EN") == "en"
    assert normalize_locale(" ru ") == "ru"


@pytest.mark.parametrize("value", ["", "fr", "russian", None])
def test_normalize_locale_rejects_unknown_values(value: str | None):
    assert normalize_locale(value) is None


def test_translate_uses_selected_locale():
    assert translate("ru", "lang.changed.ru") == "Язык изменён на русский."


def test_translate_formats_parameters():
    assert translate("en", "command.unknown", command="привет") == "Unknown command: привет"


def test_translate_falls_back_to_english_for_unknown_locale():
    assert translate("fr", "lang.changed.en") == "Language changed to English."


def test_catalogs_have_same_keys():
    english_keys = set(CATALOG["en"])
    russian_keys = set(CATALOG["ru"])
    assert russian_keys == english_keys
