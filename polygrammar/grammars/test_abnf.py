from textwrap import dedent

import pytest
from abnf.grammars import (
    rfc2616,
    rfc3339,
    rfc3629,
    rfc3986,
    rfc3987,
    rfc4647,
    rfc5234,
    rfc5322,
    rfc5646,
    rfc5987,
    rfc6265,
    rfc6266,
    rfc7230,
    rfc7231,
    rfc7232,
    rfc7233,
    rfc7234,
    rfc7235,
    rfc7405,
    rfc7489,
    rfc8187,
    rfc9051,
    rfc9110,
    rfc9111,
    rfc9116,
)

from polygrammar.grammars.abnf import PARSER, STRICT_ABNF_GRAMMAR, parse_abnf, to_abnf
from polygrammar.model import *

ABNF_GRAMMAR_STR = r"""
; Rules
rulelist = 1*( rule / (*WSP c-nl) )
rule = rulename defined-as elements c-nl
rulename = ALPHA *( ALPHA / DIGIT / "-" )
defined-as = *c-wsp ( "=" / "=/" ) *c-wsp

; Expressions
elements = alternation *WSP
alternation = concatenation *( *c-wsp "/" *c-wsp concatenation )
concatenation = repetition *( 1*c-wsp repetition )
repetition = [ repeat ] element
repeat = ( 1*DIGIT / ( *DIGIT "*" *DIGIT ) )
element = ( rulename / group / option / char-val / num-val / prose-val )
group = "(" *c-wsp alternation *c-wsp ")"
option = "[" *c-wsp alternation *c-wsp "]"

; Strings
char-val = ( case-sensitive-string / case-insensitive-string )
case-sensitive-string = "%s" quoted-string
case-insensitive-string = [ "%i" ] quoted-string
quoted-string = DQUOTE *(%x20-21 / %x23-7E ) DQUOTE

; Numeric values.
num-val = "%" ( bin-val / dec-val / hex-val )
bin-val = "b" 1*BIT [ 1*( "." 1*BIT ) / ( "-" 1*BIT ) ]
dec-val = "d" 1*DIGIT [ 1*( "." 1*DIGIT ) / ( "-" 1*DIGIT ) ]
hex-val = "x" 1*HEXDIG [ 1*( "." 1*HEXDIG ) / ( "-" 1*HEXDIG ) ]

; Prose placeholder.
prose-val = "<" *( %x20-3D / %x3F-7E ) ">"

; Whitespace
c-wsp = [ c-nl ] WSP
c-nl = ( comment / nl )
nl = CRLF
comment = ";" *( VCHAR / WSP ) nl

; ASCII character sets
WSP = %x20 / %x09
BIT = "0" / "1"
DIGIT = %x30-39
HEXDIG = %x30-39 / %x41-46 / %x61-66
VCHAR = %x21-7E
ALPHA = %x41-5A / %x61-7A
CR = %x0D
LF = %x0A
CRLF = CR LF
HTAB = %x09
SP = %x20
DQUOTE = %x22
LWSP = *( WSP / ( CRLF WSP ) )
OCTET = %x00-FF
CHAR = %x01-7F
CTL = %x00-1F / %x7F
"""


@pytest.mark.parametrize(
    "text, want",
    [
        ("abc", Symbol("abc")),
        ("abc-def-123-", Symbol("abc-def-123-")),
        ('"abc def ghi"', String("abc def ghi")),
        ('%s"abc def ghi"', String("abc def ghi")),
        ('%i"abc def ghi"', String("abc def ghi")),
        ("%x41", String("A")),
        ("%x41.42.43", String("ABC")),
        ("%x41-5A", Charset.create(CharRange.create("A", "Z"))),
        ("< prose  \\ text \"'&gt; >", String(" prose  \\ text \"'&gt; ")),
        ("[ a b c ]", Optional.create(Symbol("a"), Symbol("b"), Symbol("c"))),
        ("( a b c )", Cat.create(Symbol("a"), Symbol("b"), Symbol("c"))),
        ("(*a)", ZeroOrMore.create(Symbol("a"))),
        ("(1*a)", OneOrMore.create(Symbol("a"))),
        ("(1*2a)", Repeat.create(Symbol("a"), min=1, max=2)),
        ("(10*20a)", Repeat.create(Symbol("a"), min=10, max=20)),
        ("(*1a)", Optional.create(Symbol("a"))),
        ("(1a)", Repeat.create(Symbol("a"), min=1, max=1)),
        ("(4a)", Repeat.create(Symbol("a"), min=4, max=4)),
    ],
)
def test_parse_abnf_expression(text, want):
    (got,), _ = PARSER.first_parse(text, start="element")
    assert got == want


@pytest.mark.parametrize(
    "text, want",
    [
        (
            "foo = a b c",
            Grammar(
                [Rule.create("foo", Cat.create(Symbol("a"), Symbol("b"), Symbol("c")))]
            ),
        ),
        (
            dedent(
                """\
                foo = a b c
                foo =/ d e f
                """
            ),
            Grammar(
                [
                    Rule.create(
                        "foo", Cat.create(Symbol("a"), Symbol("b"), Symbol("c"))
                    ),
                    Rule.create(
                        "foo",
                        Cat.create(Symbol("d"), Symbol("e"), Symbol("f")),
                        is_additional_alt=True,
                    ),
                ]
            ),
        ),
        (
            dedent(
                """\
                ; comment
                foo = a b c ; comment
                ; comment
                """
            ),
            Grammar(
                [Rule.create("foo", Cat.create(Symbol("a"), Symbol("b"), Symbol("c")))]
            ),
        ),
    ],
)
def test_parse_abnf(text, want):
    assert parse_abnf(text) == want


def test_parse_abnf_grammar():
    assert parse_abnf(ABNF_GRAMMAR_STR) == STRICT_ABNF_GRAMMAR


def test_self_parse():
    text = to_abnf(STRICT_ABNF_GRAMMAR)
    assert parse_abnf(text, strict_newlines=True) == STRICT_ABNF_GRAMMAR


@pytest.mark.parametrize(
    "id, text",
    [
        ("rfc5234", rfc5234.Rule.grammar),
        ("rfc2616", rfc2616.Rule.grammar),
        ("rfc3339", rfc3339.Rule.grammar),
        ("rfc3629", rfc3629.Rule.grammar),
        ("rfc3986", rfc3986.Rule.grammar),
        ("rfc3987", rfc3987.Rule.grammar),
        ("rfc4647", rfc4647.Rule.grammar),
        ("rfc5322", rfc5322.Rule.grammar),
        ("rfc5646", rfc5646.Rule.grammar),
        ("rfc5987", rfc5987.Rule.grammar),
        ("rfc6265", rfc6265.Rule.grammar),
        ("rfc6266", rfc6266.Rule.grammar),
        ("rfc7230", rfc7230.Rule.grammar),
        ("rfc7231", rfc7231.Rule.grammar),
        ("rfc7232", rfc7232.Rule.grammar),
        ("rfc7233", rfc7233.Rule.grammar),
        ("rfc7234", rfc7234.Rule.grammar),
        ("rfc7235", rfc7235.Rule.grammar),
        ("rfc7405", rfc7405.Rule.grammar),
        ("rfc7489", rfc7489.Rule.grammar),
        ("rfc8187", rfc8187.Rule.grammar),
        ("rfc9051", rfc9051.Rule.grammar),
        ("rfc9110", rfc9110.Rule.grammar),
        ("rfc9111", rfc9111.Rule.grammar),
        ("rfc9116", rfc9116.Rule.grammar),
    ],
)
def test_parse_declaresub_abnf_grammars(id, text):
    if isinstance(text, list):
        text = "\n".join(text)
    parse_abnf(text)
