import pytest

from polygrammar.grammars.escapes import (
    DUPLICATE_DOUBLE_QUOTE_ESCAPE,
    DUPLICATE_SINGLE_QUOTE_ESCAPE,
    PYTHON_SINGLE_CHAR_ESCAPES,
    SingleCharBackslash,
)


@pytest.mark.parametrize(
    "text, want",
    [
        ("abc", "abc"),
        ('"', '""'),
        ('--> "\'" <--', '--> ""\'"" <--'),
    ],
)
def test_duplicate_double_quote(text, want):
    serialized = DUPLICATE_DOUBLE_QUOTE_ESCAPE.serialize(text)
    assert serialized == want
    parsed = DUPLICATE_DOUBLE_QUOTE_ESCAPE.parse(serialized)
    assert parsed == text


@pytest.mark.parametrize(
    "text, want",
    [
        ("abc", "abc"),
        ("'", "''"),
        ("--> '\"' <--", "--> ''\"'' <--"),
    ],
)
def test_duplicate_single_quote(text, want):
    serialized = DUPLICATE_SINGLE_QUOTE_ESCAPE.serialize(text)
    assert serialized == want
    parsed = DUPLICATE_SINGLE_QUOTE_ESCAPE.parse(serialized)
    assert parsed == text


@pytest.fixture(scope="session")
def python_single_char_escape():
    return SingleCharBackslash(PYTHON_SINGLE_CHAR_ESCAPES)


@pytest.mark.parametrize(
    "text, want",
    [
        ("abc", "abc"),
        ("\\", r"\\"),
        (
            "horizontal space: [ \t\f], vertical space: [\r\n\v], controls: [\a\b]",
            r"horizontal space: [ \t\f], vertical space: [\r\n\v], controls: [\a\b]",
        ),
    ],
)
def test_single_char_slash(text, want, python_single_char_escape):
    serialized = python_single_char_escape.serialize(text)
    assert serialized == want
    parsed = python_single_char_escape.parse(serialized)
    assert parsed == text


def test_parse_single_char_slash_unknown(python_single_char_escape):
    text = r"unknown escapes: [\x\u\U\p\q\N\1\5\d\s\S]"
    want = "unknown escapes: [xuUpqN15dsS]"
    parsed = python_single_char_escape.parse(text)
    assert parsed == want
