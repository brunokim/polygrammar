from polygrammar.model import *
from polygrammar.recursive_parser import Parser


def test_parse_string():
    parser = Parser(Grammar.create(s=String("A")))
    (got,) = parser.first_full_parse("A")
    assert got == ("s", "A")
