import pytest

from polygrammar.grammars.abnf import PARSER
from polygrammar.model import *

ABNF_GRAMMAR_STR = r"""
; Rules
rulelist = 1*( rule / (WSP* c-nl) )
rule = rulename defined-as elements c-nl
rulename = ALPHA *( ALPHA / DIGIT / "-" )
defined-as = *c-wsp ( "=" / "=/" ) *c-wsp

; Expressions
elements = alternation *WSP
alternation = concatenation *( *c-wsp "/" *c-wsp concatenation )
concatenation = repetition *( c-wsp+ repetition )
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
prose-val = "<" *( %x20-3E / %x40-7E ) ">"

; Whitespace
c-wsp = [ c-nl ] WSP
c-nl = ( comment / CRLF )
comment = ";" *( VCHAR / WSP ) CRLF

; ASCII character sets
WSP = %x20 / %x09
BIT = "0" / "1"
DIGIT = %x30-39
HEXDIG = %x30-39 / %x41-46
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
        pytest.param(
            "[ a b c ]",
            Optional.create(Symbol("a"), Symbol("b"), Symbol("c")),
            marks=[pytest.mark.xfail],
        ),
        pytest.param(
            "( a b c )",
            Cat.create(Symbol("a"), Symbol("b"), Symbol("c")),
            marks=[pytest.mark.xfail],
        ),
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
    (got,) = PARSER.first_full_parse(text, start="element")
    assert got == want
