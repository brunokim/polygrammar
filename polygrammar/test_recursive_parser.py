import re
from textwrap import dedent

import pytest

from polygrammar.model import *
from polygrammar.recursive_parser import ParseError, Parser


def test_parse_string():
    parser = Parser.from_grammar(Grammar.create(s=String("A")))
    (got,), _ = parser.first_parse("A")
    assert got == ("s", "A")
    with pytest.raises(ParseError):
        parser.first_parse("B", debug=False)


def test_parse_alt():
    parser = Parser.from_grammar(Grammar.create(s=Alt.create(String("A"), String("B"))))
    (got,), _ = parser.first_parse("A")
    assert got == ("s", "A")
    (got,), _ = parser.first_parse("B")
    assert got == ("s", "B")
    with pytest.raises(ParseError):
        parser.first_parse("C", debug=False)


def test_parse_cat():
    parser = Parser.from_grammar(Grammar.create(s=Cat.create(String("A"), String("B"))))
    (got,), _ = parser.first_parse("AB")
    assert got == ("s", "A", "B")
    with pytest.raises(ParseError):
        parser.first_parse("A", debug=False)


def test_parse_symbol():
    parser = Parser.from_grammar(
        Grammar.create(s=Alt.create(Cat.create(String("A"), Symbol("s")), String("!")))
    )
    (got,), _ = parser.first_parse("!")
    assert got == ("s", "!")
    (got,), _ = parser.first_parse("A!")
    assert got == ("s", "A", ("s", "!"))
    (got,), _ = parser.first_parse("AAAA!")
    assert got == ("s", "A", ("s", "A", ("s", "A", ("s", "A", ("s", "!")))))
    with pytest.raises(ParseError):
        parser.first_parse("A", debug=False)


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
    parser = Parser.from_grammar(
        Grammar.create(s=Repeat.create(String("A"), min=min, max=max))
    )
    (got,), _ = parser.first_parse(text)
    assert got == want


def test_parse_charset_char():
    parser = Parser.from_grammar(Grammar.create(s=Charset.create("a", "b", "c")))
    (got,), _ = parser.first_parse("a")
    assert got == ("s", "a")
    (got,), _ = parser.first_parse("b")
    assert got == ("s", "b")
    (got,), _ = parser.first_parse("c")
    assert got == ("s", "c")
    with pytest.raises(ParseError):
        parser.first_parse("d", debug=False)


def test_parse_charset_range():
    parser = Parser.from_grammar(
        Grammar.create(s=Charset.create(CharRange.create("a", "z")))
    )
    (got,), _ = parser.first_parse("a")
    assert got == ("s", "a")
    (got,), _ = parser.first_parse("m")
    assert got == ("s", "m")
    (got,), _ = parser.first_parse("z")
    assert got == ("s", "z")
    with pytest.raises(ParseError):
        parser.first_parse("A", debug=False)


def test_parse_charset_diff():
    parser = Parser.from_grammar(
        Grammar.create(
            s=CharsetDiff.create(
                Charset.create(CharRange.create("a", "z")),
                Charset.create("A", "m", CharRange.create("w", "z")),
            )
        )
    )
    (got,), _ = parser.first_parse("a")
    assert got == ("s", "a")
    (got,), _ = parser.first_parse("l")
    assert got == ("s", "l")
    (got,), _ = parser.first_parse("n")
    assert got == ("s", "n")
    (got,), _ = parser.first_parse("v")
    assert got == ("s", "v")
    with pytest.raises(ParseError):
        parser.first_parse("A", debug=False)
    with pytest.raises(ParseError):
        parser.first_parse("m", debug=False)
    with pytest.raises(ParseError):
        parser.first_parse("x", debug=False)
    with pytest.raises(ParseError):
        parser.first_parse("z", debug=False)


def test_parse_token():
    parser = Parser.from_grammar(
        Grammar.create(INT=OneOrMore.create(Charset.create(CharRange.create("0", "9"))))
    )
    (got,), _ = parser.first_parse("123")
    assert got == "123"


@pytest.fixture(scope="session")
def integer_parser():
    return Parser.from_grammar(
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
def test_parse_ignored(text, want, integer_parser):
    (got,), _ = integer_parser.first_parse(text)
    assert got == want


def test_first_parse():
    parser = Parser.from_grammar(
        Grammar.create(s=Optional.create("<", Symbol("s"), ">"))
    )
    text, offset = "<><<>><><>", 0
    (got,), offset = parser.first_parse(text, offset=offset)
    assert got == ("s", "<", ("s",), ">")
    assert offset == 2
    (got,), offset = parser.first_parse(text, offset=offset)
    assert got == ("s", "<", ("s", "<", ("s",), ">"), ">")
    assert offset == 6


def test_ambiguous_parse():
    parser = Parser.from_grammar(
        Grammar.create(
            s=Alt.create(
                Cat.create("A", Symbol("s")),
                Cat.create("AA", Symbol("s")),
                Cat.create("A", EndOfFile()),
            )
        )
    )
    valid_parses = [tree for tree, _ in parser.parse("AAAAA")]
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
        pytest.param(
            "ABBA",
            dedent(
                """\
                At 1:2 (1): trailing characters
                    ABBA
                     ^
                """
            ),
            marks=[pytest.mark.xfail],
        ),
        pytest.param(
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
            marks=[pytest.mark.xfail],
        ),
    ],
)
def test_parse_error(text, msg):
    parser = Parser.from_grammar(Grammar.create(s=OneOrMore(Alt.create("A", "\n"))))
    with pytest.raises(ParseError, match=f"^{re.escape(msg)}$"):
        parser.first_parse(text)


def test_no_match():
    parser = Parser.from_grammar(Grammar.create(s=OneOrMore(Alt.create("AA", "\n\n"))))

    msg1 = dedent(
        """\
        At 1:1 (0): string: 'BB' != 'AA' (case_sensitive=True) (symbol@0 > repeat@0 > alt@0 > string@0)
            BBBB
            ^
        """
    )
    msg2 = dedent(
        """\
        At 1:1 (0): string: 'BB' != '\\n\\n' (case_sensitive=True) (symbol@0 > repeat@0 > alt@0 > string@0)
            BBBB
            ^
        """
    )
    with pytest.RaisesGroup(
        pytest.RaisesExc(ParseError, match=f"^{re.escape(msg1)}$"),
        pytest.RaisesExc(ParseError, match=f"^{re.escape(msg2)}$"),
        match="^no match$",
    ):
        parser.first_parse("BBBB")


@pytest.fixture(scope="session")
def number_grammar():
    return Grammar.create(
        number=Cat.create(
            Optional.create(Symbol("sign")),
            Symbol("DIGITS"),
            Optional.create(".", Symbol("DIGITS")),
            Optional.create(
                Charset.create("e", "E"),
                Optional.create(Symbol("sign")),
                Symbol("DIGITS"),
            ),
        ),
        sign=Charset.create("+", "-"),
        DIGITS=OneOrMore.create(Charset.create(CharRange.create("0", "9"))),
    )


@pytest.fixture(scope="session")
def number_visitor():
    class NumberVisitor(Visitor):
        def visit_number(self, *args):
            args = iter(args)
            token = next(args)

            sign = "+"
            if token in {"+", "-"}:
                sign = token
                token = next(args)

            integer = token
            token = next(args, None)

            frac = "0"
            if token == ".":
                frac = next(args)
                token = next(args, None)

            exp_sign = "+"
            exponent = "0"
            if token in {"e", "E"}:
                token = next(args)
                if token in {"+", "-"}:
                    exp_sign = token
                    token = next(args)
                exponent = token
            return (sign, integer, frac, exp_sign, exponent)

        def visit_sign(self, sign):
            return sign

        def visit_DIGITS(self, token):
            return token

    return NumberVisitor()


@pytest.fixture(scope="session")
def number_parser(number_grammar, number_visitor):
    return Parser.from_grammar(number_grammar, number_visitor)


@pytest.mark.parametrize(
    "text, want",
    [
        ("1", ("+", "1", "0", "+", "0")),
        ("123", ("+", "123", "0", "+", "0")),
        ("+1", ("+", "1", "0", "+", "0")),
        ("-1", ("-", "1", "0", "+", "0")),
        ("-1.2", ("-", "1", "2", "+", "0")),
        ("1.234", ("+", "1", "234", "+", "0")),
        ("1e2", ("+", "1", "0", "+", "2")),
        ("1e+2", ("+", "1", "0", "+", "2")),
        ("1e-2", ("+", "1", "0", "-", "2")),
        ("1E-2", ("+", "1", "0", "-", "2")),
        ("1E-10", ("+", "1", "0", "-", "10")),
        ("-012.345e-67", ("-", "012", "345", "-", "67")),
    ],
)
def test_visitor(text, want, number_parser):
    (got,), _ = number_parser.first_parse(text)
    assert got == want


@pytest.mark.parametrize(
    "expr, text, want",
    [
        (String("A"), "A", ["A"]),
        (ZeroOrMore(String("A")), "AAAA", ["A", "A", "A", "A"]),
        (ZeroOrMore(String("A")), "AAAABA", ["A", "A", "A", "A"]),
        (
            ZeroOrMore(Alt.create("A", "A", "B")),
            "AAAABA",
            ["A", "A", "A", "A", "B", "A"],
        ),
        (ZeroOrMore(Alt.create("AA", "A", "B")), "AAABA", ["AA", "A", "B", "A"]),
    ],
)
def test_parse_without_grammar(expr, text, want):
    parser = Parser()
    result, _ = parser.first_parse(text, expr)
    assert result == want
