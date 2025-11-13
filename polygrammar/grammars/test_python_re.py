import re

import pytest

from polygrammar.grammars.python_re_writer import to_python_re
from polygrammar.model import *


@pytest.mark.parametrize(
    "expr, pattern, should_match",
    [
        (Alt.create(String("ab"), String("cd")), r"ab|cd", ["ab", "cd"]),
        (Cat.create(String("ab"), String("cd")), r"abcd", ["abcd"]),
        (
            Cat.create(String("ab").set_meta("i"), String("cd")),
            r"(?i:ab)cd",
            ["abcd", "ABcd", "aBcd"],
        ),
        (Charset.create(Char("a"), Char("b"), Char("c")), r"[abc]", ["a", "b", "c"]),
        (Charset.create(CharRange.create("0", "9")), r"[0-9]", ["1", "3", "9"]),
        (
            Charset.create(Char("^"), Char("-"), Char("\\"), Char("]")),
            r"[\^\-\\\]]",
            ["^", "-", "\\", "]"],
        ),
        (
            Charset.create(Char("-"), Char("]"), Char("^")),
            r"[\-\]\^]",
            ["^", "-", "]"],
        ),
        (
            OneOrMore.create(Charset.create(CharRange.create("0", "9"))),
            r"[0-9]+",
            ["1", "123", "987123"],
        ),
    ],
)
def test_to_python_re(expr, pattern, should_match):
    got = to_python_re(expr)
    assert got == pattern
    for s in should_match:
        assert re.fullmatch(pattern, s)
