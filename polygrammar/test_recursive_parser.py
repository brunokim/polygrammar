import re
from textwrap import dedent

import pytest

from polygrammar.model import *
from polygrammar.recursive_parser import ParseError, Parser


def test_parse_string():
    parser = Parser(Grammar.create(s=String("A")))
    (got,) = parser.first_full_parse("A")
    assert got == ("s", "A")
    with pytest.raises(ParseError):
        parser.first_full_parse("B")


def test_parse_alt():
    parser = Parser(Grammar.create(s=Alt.create(String("A"), String("B"))))
    (got,) = parser.first_full_parse("A")
    assert got == ("s", "A")
    (got,) = parser.first_full_parse("B")
    assert got == ("s", "B")
    with pytest.raises(ParseError):
        parser.first_full_parse("C")


def test_parse_cat():
    parser = Parser(Grammar.create(s=Cat.create(String("A"), String("B"))))
    (got,) = parser.first_full_parse("AB")
    assert got == ("s", "A", "B")
    with pytest.raises(ParseError):
        parser.first_full_parse("A")


def test_parse_symbol():
    parser = Parser(
        Grammar.create(s=Alt.create(Cat.create(String("A"), Symbol("s")), String("!")))
    )
    (got,) = parser.first_full_parse("!")
    assert got == ("s", "!")
    (got,) = parser.first_full_parse("A!")
    assert got == ("s", "A", ("s", "!"))
    (got,) = parser.first_full_parse("AAAA!")
    assert got == ("s", "A", ("s", "A", ("s", "A", ("s", "A", ("s", "!")))))
    with pytest.raises(ParseError):
        parser.first_full_parse("A")


@pytest.mark.parametrize(
    "min, max, text, want",
    [
        (0, None, "", ("s",)),
        (1, None, "A", ("s", "A")),
        (1, None, "AA", ("s", "A", "A")),
        (2, None, "AA", ("s", "A", "A")),
        (0, 1, "", ("s",)),
        (0, 1, "A", ("s", "A")),
        (1, 1, "A", ("s", "A")),
        (1, 5, "A", ("s", "A")),
        (1, 5, "AA", ("s", "A", "A")),
        (1, 5, "AAAAA", ("s", "A", "A", "A", "A", "A")),
    ],
)
def test_parse_repeat(min, max, text, want):
    parser = Parser(Grammar.create(s=Repeat.create(String("A"), min=min, max=max)))
    (got,) = parser.first_full_parse(text)
    assert got == want


def test_parse_charset_char():
    parser = Parser(Grammar.create(s=Charset.create("a", "b", "c")))
    (got,) = parser.first_full_parse("a")
    assert got == ("s", "a")
    (got,) = parser.first_full_parse("b")
    assert got == ("s", "b")
    (got,) = parser.first_full_parse("c")
    assert got == ("s", "c")
    with pytest.raises(ParseError):
        parser.first_full_parse("d")


def test_parse_charset_range():
    parser = Parser(Grammar.create(s=Charset.create(CharRange.create("a", "z"))))
    (got,) = parser.first_full_parse("a")
    assert got == ("s", "a")
    (got,) = parser.first_full_parse("m")
    assert got == ("s", "m")
    (got,) = parser.first_full_parse("z")
    assert got == ("s", "z")
    with pytest.raises(ParseError):
        parser.first_full_parse("A")


def test_parse_charset_diff():
    parser = Parser(
        Grammar.create(
            s=CharsetDiff.create(
                Charset.create(CharRange.create("a", "z")),
                Charset.create("A", "m", CharRange.create("w", "z")),
            )
        )
    )
    (got,) = parser.first_full_parse("a")
    assert got == ("s", "a")
    (got,) = parser.first_full_parse("l")
    assert got == ("s", "l")
    (got,) = parser.first_full_parse("n")
    assert got == ("s", "n")
    (got,) = parser.first_full_parse("v")
    assert got == ("s", "v")
    with pytest.raises(ParseError):
        parser.first_full_parse("A")
    with pytest.raises(ParseError):
        parser.first_full_parse("m")
    with pytest.raises(ParseError):
        parser.first_full_parse("x")
    with pytest.raises(ParseError):
        parser.first_full_parse("z")


def test_parse_token():
    parser = Parser(
        Grammar.create(INT=OneOrMore.create(Charset.create(CharRange.create("0", "9"))))
    )
    (got,) = parser.first_full_parse("123")
    assert got == "123"


@pytest.fixture(scope="session")
def number_parser():
    return Parser(
        Grammar.create(
            INT=OneOrMore(Alt.create(Symbol("digit"), Symbol("_separator"))),
            digit=Charset.create(CharRange.create("0", "9")),
            _separator=Charset.create(" ", "_"),
        )
    )


@pytest.mark.parametrize(
    "text, want",
    [
        ("1", "1"),
        ("123", "123"),
        ("1_234", "1234"),
        ("1 234 567", "1234567"),
    ],
)
def test_parse_ignored(text, want, number_parser):
    (got,) = number_parser.first_full_parse(text)
    assert got == want


def test_first_parse():
    parser = Parser(Grammar.create(s=Optional.create("<", Symbol("s"), ">")))
    text, offset = "<><<>><><>", 0
    (got,), offset = parser.first_parse(text, offset=offset)
    assert got == ("s", "<", ("s",), ">")
    assert offset == 2
    (got,), offset = parser.first_parse(text, offset=offset)
    assert got == ("s", "<", ("s", "<", ("s",), ">"), ">")
    assert offset == 6


def test_ambiguous_parse():
    parser = Parser(
        Grammar.create(
            s=Alt.create(
                Cat.create("A", Symbol("s")), Cat.create("AA", Symbol("s")), "A"
            )
        )
    )
    valid_parses = list(parser.full_parse("AAAAA"))
    assert valid_parses == [
        [("s", "A", ("s", "A", ("s", "A", ("s", "A", ("s", "A")))))],
        [("s", "A", ("s", "A", ("s", "AA", ("s", "A"))))],
        [("s", "A", ("s", "AA", ("s", "A", ("s", "A"))))],
        [("s", "AA", ("s", "A", ("s", "A", ("s", "A"))))],
        [("s", "AA", ("s", "AA", ("s", "A")))],
    ]


@pytest.mark.parametrize(
    "text, msg",
    [
        (
            "ABBA",
            dedent(
                """\
                At 1:2 (1): trailing characters
                    ABBA
                     ^
                """
            ),
        ),
        (
            "BBBBB",
            dedent(
                """\
                At 1:1 (0): no match
                    BBBBB
                    ^
                """
            ),
        ),
        (
            dedent(
                """\
                AAAAA
                AABAA
                """
            ),
            dedent(
                """\
                At 2:3 (8): trailing characters
                    AABAA
                      ^
                """
            ),
        ),
    ],
)
def test_parse_error(text, msg):
    parser = Parser(Grammar.create(s=OneOrMore(Alt.create("A", "\n"))))
    with pytest.raises(ParseError, match=f"^{re.escape(msg)}$"):
        parser.first_full_parse(text)
