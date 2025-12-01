import re

from multimethod import multimethod

from polygrammar.grammars.escapes import (
    UNICODE_BACKSLASH_ESCAPE,
    CombinedEscapes,
    SingleCharBackslash,
)
from polygrammar.model import *
from polygrammar.model import is_case_sensitive

# Escapes

CHAR_ESCAPE = CombinedEscapes(
    [
        SingleCharBackslash({"-": "-", "]": "]", "^": "^", "\\": "\\"}),
        UNICODE_BACKSLASH_ESCAPE,
    ]
)


# python_re_priority


@multimethod
def python_re_priority(self: object) -> int:
    return 0


@multimethod
def python_re_priority(self: Alt) -> int:
    return 100


@multimethod
def python_re_priority(self: Diff) -> int:
    return 75


@multimethod
def python_re_priority(self: Cat) -> int:
    return 50


@multimethod
def python_re_priority(self: Repeat | Optional | ZeroOrMore | OneOrMore) -> int:
    return 25


# to_python_re


@multimethod
def to_python_re(self: Expr, parent_priority: int) -> str:
    if python_re_priority(self) > parent_priority:
        return "(?:" + to_python_re(self) + ")"
    return to_python_re(self)


@multimethod
def to_python_re(self: Alt):
    exprs = (to_python_re(expr, python_re_priority(self)) for expr in self.exprs)
    return "|".join(exprs)


@multimethod
def to_python_re(self: Cat) -> str:
    exprs = (to_python_re(expr, python_re_priority(self)) for expr in self.exprs)
    return "".join(exprs)


@multimethod
def to_python_re(self: Optional) -> str:
    expr = to_python_re(self.expr, python_re_priority(self))
    return expr + "?"


@multimethod
def to_python_re(self: ZeroOrMore) -> str:
    expr = to_python_re(self.expr, python_re_priority(self))
    return expr + "*"


@multimethod
def to_python_re(self: OneOrMore) -> str:
    expr = to_python_re(self.expr, python_re_priority(self))
    return expr + "+"


@multimethod
def to_python_re(self: Repeat) -> str:
    expr = to_python_re(self.expr, python_re_priority(self))
    min = str(self.min) if self.min != 0 else ""
    max = str(self.max) if self.max is not None else ""
    if min and max and min == max:
        return expr + "{" + min + "}"
    return expr + "{" + min + "," + max + "}"


@multimethod
def to_python_re(self: String) -> str:
    if is_case_sensitive(self):
        return re.escape(self.value)
    return "(?i:" + re.escape(self.value) + ")"


@multimethod
def to_python_re(self: Regexp) -> str:
    return self.pattern


@multimethod
def to_python_re(self: Char) -> str:
    ch = self.char
    return CHAR_ESCAPE.serialize(ch)


@multimethod
def to_python_re(self: CharRange) -> str:
    return to_python_re(self.start) + "-" + to_python_re(self.end)


@multimethod
def to_python_re(self: Charset) -> str:
    groups = "".join(to_python_re(g) for g in self.groups)
    return "[" + groups + "]"
