from multimethod import multimethod

from polygrammar.grammars.escapes import (
    DUPLICATE_DOUBLE_QUOTE_ESCAPE,
    PYTHON_SINGLE_CHAR_ESCAPES,
    UNICODE_BACKSLASH_ESCAPE,
    CombinedEscapes,
    SingleCharBackslash,
)
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

__all__ = ["parse_lisp_data", "parse_lisp_grammar", "LISP_GRAMMAR"]


# Escapes

ESCAPE = CombinedEscapes(
    [
        DUPLICATE_DOUBLE_QUOTE_ESCAPE,
        SingleCharBackslash(PYTHON_SINGLE_CHAR_ESCAPES),
        UNICODE_BACKSLASH_ESCAPE,
    ]
)


#         parse_data       parse_grammar
# .--------.-----> .--------.-----> .---------.
# |  text  |       |  lisp  |       | grammar |
# '--------' <-----'--------' <-----'---------'
#          lisp_str          to_lisp

# to_lisp


lisp_name = {
    "symbol": Symbol,
    "string": String,
    "char": Char,
    "end_of_file": EndOfFile,
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
def to_lisp(self: Symbol):
    return self


@multimethod
def to_lisp(self: String):
    return self.value


@multimethod
def to_lisp(self: Alt):
    return (Symbol("alt"),) + tuple(to_lisp(expr) for expr in self.exprs)


@multimethod
def to_lisp(self: Cat):
    return (Symbol("cat"),) + tuple(to_lisp(expr) for expr in self.exprs)


@multimethod
def to_lisp(self: Repeat):
    return (Symbol("repeat"), to_lisp(self.expr), self.min, self.max)


@multimethod
def to_lisp(self: Optional):
    return (Symbol("optional"), to_lisp(self.expr))


@multimethod
def to_lisp(self: ZeroOrMore):
    return (Symbol("zero_or_more"), to_lisp(self.expr))


@multimethod
def to_lisp(self: OneOrMore):
    return (Symbol("one_or_more"), to_lisp(self.expr))


@multimethod
def to_lisp(self: Char):
    return (Symbol("char"), self.char)


@multimethod
def to_lisp(self: CharRange):
    return (Symbol("char_range"), to_lisp(self.start), to_lisp(self.end))


@multimethod
def to_lisp(self: Charset):
    return (Symbol("charset"),) + tuple(to_lisp(g) for g in self.groups)


@multimethod
def to_lisp(self: Diff):
    return (Symbol("diff"), to_lisp(self.base), to_lisp(self.diff))


@multimethod
def to_lisp(self: CharsetDiff):
    return (Symbol("charset_diff"), to_lisp(self.base), to_lisp(self.diff))


@multimethod
def to_lisp(self: Rule):
    return (Symbol("rule"), to_lisp(self.name), to_lisp(self.expr))


@multimethod
def to_lisp(self: Grammar):
    return (Symbol("grammar"),) + tuple(to_lisp(rule) for rule in self.rules)


# Format Lisp data

MAX_WIDTH = 80


def lisp_str(obj):
    if isinstance(obj, String):
        obj = obj.value
    if isinstance(obj, str):
        content = ESCAPE.serialize(obj)
        return f'"{content}"'
    if isinstance(obj, Symbol):
        return obj.name
    if not isinstance(obj, tuple):
        return repr(obj)

    args = [lisp_str(x) for x in obj]

    has_newline = any("\n" in arg for arg in args)
    width = sum(len(arg) + 1 for arg in args) + 2 - 1
    if has_newline or width > MAX_WIDTH:
        sep = "\n  "
        args = (s.replace("\n", sep) for s in args)
    else:
        sep = " "

    args_str = sep.join(args)
    return f"({args_str})"


# Grammar, visitor, parser

symbol = Symbol
string = String
alt = Alt.create
cat = Cat.create
optional = Optional.create
zero_or_more = ZeroOrMore.create
one_or_more = OneOrMore.create
charset = Charset.create
char_range = CharRange.create
charset_diff = CharsetDiff.create
rule = Rule.create
grammar = Grammar.create


LISP_GRAMMAR = grammar(
    values=cat(symbol("_"), zero_or_more(symbol("annotated_value"), symbol("_"))),
    term=cat(
        string("("),
        symbol("_"),
        optional(
            symbol("annotated_value"),
            zero_or_more(symbol("_1"), symbol("annotated_value")),
            symbol("_"),
        ),
        string(")"),
    ),
    annotated_value=cat(
        zero_or_more("#", symbol("value"), symbol("_")), symbol("value")
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
        zero_or_more(
            alt(
                charset_diff(symbol("CHAR"), '"', "\\"),
                string('""'),
                cat(string("\\"), symbol("CHAR")),
            )
        ),
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
    def visit_values(self, *values):
        return values

    def visit_term(self, *values):
        return values[1:-1]  # Remove parenthesis

    def visit_annotated_value(self, *values):
        annotations = values[:-1]
        value = values[-1]
        if annotations and isinstance(value, str):
            # Convert to String to append annotations.
            value = String(value)
        for i in range(1, len(annotations), 2):
            value.__meta__.append(annotations[i])
        return value

    def visit_value(self, value):
        return value

    def visit_SYMBOL(self, token):
        return Symbol(token)

    def visit_STRING(self, token):
        value = token[1:-1]
        value = ESCAPE.parse(value)
        return value


class LispGrammarVisitor(LispVisitor):
    def visit_term(self, *values):
        values = super().visit_term(*values)
        match values:
            case [Symbol(name) | name, *args] if name in lisp_name:
                cls = lisp_name[name]
                if name in {"symbol", "string", "char", "end_of_file"}:
                    return cls(*args)
                args = (arg.value if isinstance(arg, String) else arg for arg in args)
                return cls.create(*args)
            case _:
                return values


DATA_PARSER = Parser.from_grammar(LISP_GRAMMAR, LispVisitor())
GRAMMAR_PARSER = Parser.from_grammar(LISP_GRAMMAR, LispGrammarVisitor())


def parse_lisp_grammar(text):
    (node,) = GRAMMAR_PARSER.first_full_parse(text)
    (grammar,) = node
    return grammar


def parse_lisp_data(text):
    (node,) = DATA_PARSER.first_full_parse(text)
    (grammar,) = node
    return grammar
