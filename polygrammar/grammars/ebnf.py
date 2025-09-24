from multimethod import multimethod

from polygrammar.grammars.escapes import (
    SLASH_ESCAPES,
    make_escapes_pattern,
    replace_escapes,
    reverse_escapes,
)
from polygrammar.grammars.lisp import parse_lisp
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

__all__ = ["to_ebnf", "parse_ebnf", "PARSER", "EBNF_GRAMMAR", "EbnfVisitor"]

# Escapes

_DQUOTE_STRING_ESCAPES = SLASH_ESCAPES | {'"': '""'}
_SQUOTE_STRING_ESCAPES = SLASH_ESCAPES | {"'": "''"}
_CHAR_ESCAPES = SLASH_ESCAPES | {"-": r"\-", "]": r"\]"}

_DQUOTE_STRING_REVERSE_ESCAPES = reverse_escapes(_DQUOTE_STRING_ESCAPES)
_SQUOTE_STRING_REVERSE_ESCAPES = reverse_escapes(_SQUOTE_STRING_ESCAPES)
_CHAR_REVERSE_ESCAPES = reverse_escapes(_CHAR_ESCAPES)

_DQUOTE_STRING_PATTERN = make_escapes_pattern(_DQUOTE_STRING_ESCAPES)
_SQUOTE_STRING_PATTERN = make_escapes_pattern(_SQUOTE_STRING_ESCAPES)
_DQUOTE_STRING_REVERSE_PATTERN = make_escapes_pattern(_DQUOTE_STRING_REVERSE_ESCAPES)
_SQUOTE_STRING_REVERSE_PATTERN = make_escapes_pattern(_SQUOTE_STRING_REVERSE_ESCAPES)

# ebnf_priority


@multimethod
def ebnf_priority(self: object) -> int:
    return 0


@multimethod
def ebnf_priority(self: Alt) -> int:
    return 100


@multimethod
def ebnf_priority(self: CharsetDiff) -> int:
    return 75


@multimethod
def ebnf_priority(self: Cat) -> int:
    return 50


@multimethod
def ebnf_priority(self: Repeat) -> int:
    return 25


# to_ebnf


@multimethod
def to_ebnf(self: Expr, parent_priority: int) -> str:
    if ebnf_priority(self) > parent_priority:
        return "(" + to_ebnf(self) + ")"
    return to_ebnf(self)


@multimethod
def to_ebnf(self: object) -> str:
    return f"? {self} ?"


@multimethod
def to_ebnf(self: Alt) -> str:
    exprs = (to_ebnf(expr, ebnf_priority(self)) for expr in self.exprs)
    return " | ".join(exprs)


@multimethod
def to_ebnf(self: Cat) -> str:
    exprs = (to_ebnf(expr, ebnf_priority(self)) for expr in self.exprs)
    return " ".join(exprs)


@multimethod
def to_ebnf(self: Repeat) -> str:
    expr = to_ebnf(self.expr, ebnf_priority(self))
    min = str(self.min) if self.min != 0 else ""
    max = str(self.max) if self.max is not None else ""
    if min and max and min == max:
        return expr + "{" + min + "}"
    return expr + "{" + min + "," + max + "}"


@multimethod
def to_ebnf(self: Optional) -> str:
    expr = to_ebnf(self.expr, ebnf_priority(self))
    return expr + "?"


@multimethod
def to_ebnf(self: ZeroOrMore) -> str:
    expr = to_ebnf(self.expr, ebnf_priority(self))
    return expr + "*"


@multimethod
def to_ebnf(self: OneOrMore) -> str:
    expr = to_ebnf(self.expr, ebnf_priority(self))
    return expr + "+"


@multimethod
def to_ebnf(self: Symbol) -> str:
    return self.name


@multimethod
def to_ebnf(self: String) -> str:
    dquote_count = 0
    squote_count = 0
    for ch in self.value:
        if ch == '"':
            dquote_count += 1
            continue
        if ch == "'":
            squote_count += 1
            continue

    if dquote_count < squote_count:
        quote = '"'
        pattern = _DQUOTE_STRING_PATTERN
        escapes = _DQUOTE_STRING_ESCAPES
    else:
        quote = "'"
        pattern = _SQUOTE_STRING_PATTERN
        escapes = _SQUOTE_STRING_ESCAPES

    escaped = replace_escapes(pattern, escapes, self.value)
    return quote + escaped + quote


@multimethod
def to_ebnf(self: Char) -> str:
    ch = self.char
    return _CHAR_ESCAPES.get(ch, ch)


@multimethod
def to_ebnf(self: CharRange) -> str:
    return to_ebnf(self.start) + "-" + to_ebnf(self.end)


@multimethod
def to_ebnf(self: Charset) -> str:
    groups = "".join(to_ebnf(g) for g in self.groups)
    return "[" + groups + "]"


@multimethod
def to_ebnf(self: CharsetDiff) -> str:
    return to_ebnf(self.base) + " - " + to_ebnf(self.diff)


@multimethod
def to_ebnf(self: Rule) -> str:
    return to_ebnf(self.name) + " = " + to_ebnf(self.expr)


@multimethod
def to_ebnf(self: Grammar) -> str:
    size = max(len(rule.name.name) for rule in self.rules)
    rules = (f"{rule.name.name:<{size}s} = {to_ebnf(rule.expr)}" for rule in self.rules)
    return " ;\n".join(rules) + " ;"


EBNF_GRAMMAR = parse_lisp(
    r'''
    (grammar
      (rule grammar _ (one_or_more rule _ ";" _))
      (rule rule SYMBOL _ "=" _ expr)

      ; Expressions
      (rule expr alt)
      (rule alt cat (zero_or_more _ "|" _ cat))
      (rule cat term (zero_or_more _1 term))
      (rule term (alt repeat diff atom))
      (rule repeat atom (alt "*" "+" "?" min_max))
      (rule min_max "{" (optional NUMBER) "," (optional NUMBER) "}")
      (rule diff atom (one_or_more _ "-" _ atom))
      (rule atom (alt SYMBOL STRING charset (cat "(" _ expr _ ")")))

      ; Symbol uses C syntax.
      (rule SYMBOL (alt letter "_") (zero_or_more (alt letter digit "_")))

      ; String may use double or single quotes. Escape a quote by doubling it or with backslash.
      (rule STRING (alt dquote_string squote_string))
      (rule dquote_string
        """"
        (zero_or_more
          (alt
            (charset_diff CHAR """" "\\")
            """"""
            (cat "\\" CHAR)))
        """")
      (rule squote_string
        "'"
        (zero_or_more
          (alt (charset_diff CHAR "'" "\\") "''" (cat "\\" CHAR)))
        "'")

      ; Charset use a limited regex syntax.
      ; - "^" for negation is not supported; use a diff '-' instead.
      ; - "-" always needs to be escaped, independent of its position.
      (rule charset "[" (one_or_more charset_group) "]")
      (rule charset_group (alt char_range CHARSET_CHAR))
      (rule CHARSET_CHAR
        (alt
          (charset_diff CHAR "]" "-" "\")
          (cat "\" CHAR)))
      (rule char_range CHARSET_CHAR "-" CHARSET_CHAR)

      ; Number is a sequence of digits.
      (rule NUMBER (one_or_more digit))

      ; Whitespace
      (rule _ (zero_or_more (alt space comment)))
      (rule _1 (one_or_more (alt space comment)))
      (rule comment (alt line_comment block_comment))
      (rule line_comment "#" (zero_or_more CHAR) "\n")
      (rule block_comment
        "/*"
        (zero_or_more
          (alt
            (charset_diff CHAR1 "*")
            (cat "*" (charset_diff CHAR1 "/"))))
        (optional "*")
        "*/")

      ; ASCII character classes
      (rule letter (charset (char_range "a" "z") (char_range "A" "Z")))
      (rule digit (charset (char_range "0" "9")))
      (rule space (charset " " "\t" "\n" "\r"))
      (rule CHAR (charset (char_range "!" "~") " " "\t"))
      (rule CHAR1 (charset (char_range "!" "~") " " "\t" "\n" "\r"))
    )
    '''
)


class EbnfVisitor(Visitor):
    def visit_grammar(self, *rules):
        return Grammar(rule for rule in rules if rule != ";")

    def visit_rule(self, *args):
        name, _, expr = args
        return Rule(name, expr)

    def visit_expr(self, alt):
        return alt

    def visit_alt(self, term, *args):
        terms = [term]
        while args:
            _, next_term = args[:2]
            terms.append(next_term)
            args = args[2:]
        return Alt.create(*terms)

    def visit_cat(self, *terms):
        return Cat.create(*terms)

    def visit_term(self, arg):
        return arg

    def visit_repeat(self, atom, *args):
        if not args:
            return atom
        (qualifier,) = args
        match qualifier:
            case "*":
                return ZeroOrMore(atom)
            case "+":
                return OneOrMore(atom)
            case "?":
                return Optional(atom)
            case (min, max):
                return Repeat(atom, min, max)
        raise NotImplementedError("visit_repeat", args)

    def visit_min_max(self, *args):
        match args:
            case ["{", ",", "}"]:
                return 0, None
            case ["{", int() as min, ",", "}"]:
                return min, None
            case ["{", ",", int() as max, "}"]:
                return 0, max
            case ["{", int() as min, ",", int() as max, "}"]:
                return min, max

    def visit_diff(self, base, *args):
        for i in range(1, len(args), 2):
            base = CharsetDiff(base, args[i])
        return base

    def visit_atom(self, *args):
        match args:
            case [arg]:
                return arg
            case [_, atom, _]:
                return atom
        raise NotImplementedError("visit_atom", args)

    def visit_SYMBOL(self, token):
        return Symbol(token)

    def visit_STRING(self, token):
        quote = token[0]
        value = token[1:-1]
        if quote == '"':
            escapes = _DQUOTE_STRING_REVERSE_ESCAPES
            pattern = _DQUOTE_STRING_REVERSE_PATTERN
        else:
            escapes = _SQUOTE_STRING_REVERSE_ESCAPES
            pattern = _SQUOTE_STRING_REVERSE_PATTERN

        value = replace_escapes(pattern, escapes, value)
        return String(value)

    def visit_charset(self, *tokens):
        _, *groups, _ = tokens
        return Charset(groups)

    def visit_charset_group(self, group):
        return group

    def visit_CHARSET_CHAR(self, token):
        ch = _CHAR_REVERSE_ESCAPES.get(token, token)
        return Char(ch)

    def visit_char_range(self, start, _, end):
        return CharRange(start, end)

    def visit_NUMBER(self, token):
        return int(token)


PARSER = Parser(EBNF_GRAMMAR, EbnfVisitor())


def parse_ebnf(text):
    (node,) = PARSER.first_full_parse(text)
    return node
