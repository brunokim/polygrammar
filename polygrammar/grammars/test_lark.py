import pytest

from polygrammar.grammars.lark import PARSER
from polygrammar.model import *


@pytest.mark.parametrize(
    "text, want",
    [
        ("/a/", Regexp("a")),
    ],
)
def test_parse_lark_regexp(text, want):
    (got,), _ = PARSER.first_parse(text, expr=Symbol("REGEXP"))
    assert got == want
