from multimethod import multimethod

from polygrammar.grammars.escapes import (
    CODE_ESCAPE,
    DUPLICATE_DOUBLE_QUOTE_ESCAPE,
    SINGLE_CHAR_SLASH_ESCAPE,
    CombinedEscapes,
)
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

__all__ = ["parse_lisp", "PARSER", "LISP_GRAMMAR", "LispVisitor"]


# Escapes

ESCAPE = CombinedEscapes(
    [DUPLICATE_DOUBLE_QUOTE_ESCAPE, SINGLE_CHAR_SLASH_ESCAPE, CODE_ESCAPE]
)

# to_lisp


lisp_name = {
    "symbol": Symbol,
    "string": String,
    "char": Char,
    "alt": Alt,
    "|": Alt,
    "cat": Cat,
    "repeat": Repeat,
    "optional": Optional,
    "?": Optional,
    "zero_or_more": ZeroOrMore,
    "*": ZeroOrMore,
    "one_or_more": OneOrMore,
    "+": OneOrMore,
    "char_range": CharRange,
    "charset": Charset,
    "diff": Diff,
    "-": Diff,
    "charset_diff": CharsetDiff,
    "rule": Rule,
    "grammar": Grammar,
}


@multimethod
def to_lisp(self: object):
    return self


@multimethod
def to_lisp(self: Alt):
    return ("alt",) + tuple(to_lisp(expr) for expr in self.exprs)


@multimethod
def to_lisp(self: Cat):
    return ("cat",) + tuple(to_lisp(expr) for expr in self.exprs)


@multimethod
def to_lisp(self: Repeat):
    return ("repeat", to_lisp(self.expr), self.min, self.max)


@multimethod
def to_lisp(self: Optional):
    return ("optional", to_lisp(self.expr))


@multimethod
def to_lisp(self: ZeroOrMore):
    return ("zero_or_more", to_lisp(self.expr))


@multimethod
def to_lisp(self: OneOrMore):
    return ("one_or_more", to_lisp(self.expr))


@multimethod
def to_lisp(self: Symbol):
    return ("symbol", self.name)


@multimethod
def to_lisp(self: String):
    return ("string", self.value)


@multimethod
def to_lisp(self: Char):
    return ("char", self.char)


@multimethod
def to_lisp(self: CharRange):
    return ("char_range", to_lisp(self.start), to_lisp(self.end))


@multimethod
def to_lisp(self: Charset):
    return ("charset",) + tuple(to_lisp(g) for g in self.groups)


@multimethod
def to_lisp(self: Diff):
    return ("diff", to_lisp(self.base), to_lisp(self.diff))


@multimethod
def to_lisp(self: CharsetDiff):
    return ("charset_diff", to_lisp(self.base), to_lisp(self.diff))


@multimethod
def to_lisp(self: Rule):
    return ("rule", to_lisp(self.name), to_lisp(self.expr))


@multimethod
def to_lisp(self: Grammar):
    return ("grammar",) + tuple(to_lisp(rule) for rule in self.rules)


MAX_WIDTH = 80


def lisp_str(obj, level=1):
    if isinstance(obj, str):
        content = ESCAPE.serialize(obj)
        return f'"{content}"'
    if not isinstance(obj, tuple):
        return repr(obj)
    name, *args = obj
    args_str = " ".join(lisp_str(x, level) for x in args)
    has_newline = "\n" in args_str
    within_width = len(args_str) < MAX_WIDTH - level * 2
    if has_newline or not within_width:
        indent = "\n" + (level * "  ")
        args_str = indent + indent.join(lisp_str(x, level + 1) for x in args)
    return f"({name} {args_str})"


# Grammar, visitor, parser

symbol = Symbol
string = String
alt = Alt.create
cat = Cat.create
zero_or_more = ZeroOrMore.create
one_or_more = OneOrMore.create
charset = Charset.create
char_range = CharRange.create
charset_diff = CharsetDiff.create
rule = Rule.create
grammar = Grammar.create


LISP_GRAMMAR = grammar(
    terms=cat(symbol("_"), zero_or_more(symbol("term"), symbol("_"))),
    term=cat(
        string("("),
        symbol("_"),
        symbol("value"),
        zero_or_more(symbol("_1"), symbol("value")),
        symbol("_"),
        string(")"),
    ),
    value=alt(symbol("SYMBOL"), symbol("STRING"), symbol("term")),
    SYMBOL=alt(symbol("c_symbol"), symbol("operator")),
    c_symbol=cat(
        alt(symbol("letter"), string("_")),
        zero_or_more(alt(symbol("letter"), symbol("digit"), string("_"), string("-"))),
    ),
    operator=charset("+", "*", "?", "/", "|", "-", "!"),
    STRING=cat(
        string('"'),
        zero_or_more(alt(charset_diff(symbol("CHAR"), '"'), string('""'))),
        string('"'),
    ),
    _=zero_or_more(alt(symbol("space"), symbol("comment"))),
    _1=one_or_more(alt(symbol("space"), symbol("comment"))),
    comment=cat(string(";"), zero_or_more(symbol("CHAR")), string("\n")),
    letter=charset(char_range("a", "z"), char_range("A", "Z")),
    digit=charset(char_range("0", "9")),
    space=charset(" ", "\t", "\n", "\r", ","),
    CHAR=charset(char_range("\x21", "\x7e"), " ", "\t"),
)


class LispVisitor(Visitor):
    def visit_terms(self, *terms):
        return terms

    def visit_term(self, *values):
        name, *args = values[1:-1]  # Remove parenthesis
        if isinstance(name, Symbol):
            name = name.name
        cls = lisp_name[name]
        if name in {"symbol", "string", "char"}:
            return cls(*args)
        return cls.create(*args)

    def visit_value(self, value):
        return value

    def visit_SYMBOL(self, token):
        return Symbol(token)

    def visit_STRING(self, token):
        value = token[1:-1]
        value = ESCAPE.parse(value)
        return value


PARSER = Parser(LISP_GRAMMAR, LispVisitor())


def parse_lisp(text):
    (node,) = PARSER.first_full_parse(text)
    (grammar,) = node
    return grammar
