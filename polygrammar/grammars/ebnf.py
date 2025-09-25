from multimethod import multimethod

from polygrammar.grammars.escapes import (
    DUPLICATE_DOUBLE_QUOTE_ESCAPE,
    DUPLICATE_SINGLE_QUOTE_ESCAPE,
    SINGLE_CHAR_SLASH_ESCAPE,
    CombinedEscapes,
    FiniteSet,
)
from polygrammar.grammars.lisp import parse_lisp
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

__all__ = ["to_ebnf", "parse_ebnf", "PARSER", "EBNF_GRAMMAR", "EbnfVisitor"]

# Escapes

DQUOTE_STRING_ESCAPE = CombinedEscapes(
    [DUPLICATE_DOUBLE_QUOTE_ESCAPE, SINGLE_CHAR_SLASH_ESCAPE]
)
SQUOTE_STRING_ESCAPE = CombinedEscapes(
    [DUPLICATE_SINGLE_QUOTE_ESCAPE, SINGLE_CHAR_SLASH_ESCAPE]
)
CHAR_ESCAPE = CombinedEscapes(
    [FiniteSet({"-": r"\-", "]": r"\]"}), SINGLE_CHAR_SLASH_ESCAPE]
)

# ebnf_priority


@multimethod
def ebnf_priority(self: object) -> int:
    return 0


@multimethod
def ebnf_priority(self: Alt) -> int:
    return 100


@multimethod
def ebnf_priority(self: Diff) -> int:
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
        escape = DQUOTE_STRING_ESCAPE
    else:
        quote = "'"
        escape = SQUOTE_STRING_ESCAPE

    escaped = escape.serialize(self.value)
    return quote + escaped + quote


@multimethod
def to_ebnf(self: Char) -> str:
    ch = self.char
    return CHAR_ESCAPE.serialize(ch)


@multimethod
def to_ebnf(self: CharRange) -> str:
    return to_ebnf(self.start) + "-" + to_ebnf(self.end)


@multimethod
def to_ebnf(self: Charset) -> str:
    groups = "".join(to_ebnf(g) for g in self.groups)
    return "[" + groups + "]"


@multimethod
def to_ebnf(self: Diff) -> str:
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
      (rule grammar _ (+ rule _ ";" _))
      (rule rule SYMBOL _ "=" _ expr)

      ; Expressions
      (rule expr alt)
      (rule alt cat (* _ "|" _ cat))
      (rule cat term (* _1 term))
      (rule term (| repeat diff atom))
      (rule repeat atom (| "*" "+" "?" min_max))
      (rule min_max "{" (? NUMBER) "," (? NUMBER) "}")
      (rule diff atom (+ _ "-" _ atom))
      (rule atom (| SYMBOL STRING charset (cat "(" _ expr _ ")")))

      ; Symbol uses C syntax.
      (rule SYMBOL (| letter "_") (* (| letter digit "_")))

      ; String may use double or single quotes. Escape a quote by doubling it or with backslash.
      (rule STRING (| dquote_string squote_string))
      (rule dquote_string
        """"
        (* (|
          (- CHAR """" "\")
          """"""
          (cat "\" CHAR)))
        """")
      (rule squote_string
        "'"
        (* (| (- CHAR "'" "\") "''" (cat "\" CHAR)))
        "'")

      ; Charset use a limited regex syntax.
      ; - "^" for negation is not supported; use a diff '-' instead.
      ; - "-" always needs to be escaped, independent of its position.
      (rule charset "[" (+ charset_group) "]")
      (rule charset_group (| char_range CHARSET_CHAR))
      (rule CHARSET_CHAR
        (|
          (- CHAR "]" "-" "\")
          (cat "\" CHAR)))
      (rule char_range CHARSET_CHAR "-" CHARSET_CHAR)

      ; Number is a sequence of digits.
      (rule NUMBER (+ digit))

      ; Whitespace
      (rule _ (* (| space comment)))
      (rule _1 (+ (| space comment)))
      (rule comment (| line_comment block_comment))
      (rule line_comment "#" (* CHAR) "\n")
      (rule block_comment
        "/*"
        (* (|
          (- CHAR1 "*")
          (cat "*" (- CHAR1 "/"))))
        (? "*")
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
        # Jump over "-" signs.
        for i in range(1, len(args), 2):
            base = Diff(base, args[i])
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
            escape = DQUOTE_STRING_ESCAPE
        else:
            escape = SQUOTE_STRING_ESCAPE

        value = escape.parse(value)
        return String(value)

    def visit_charset(self, *tokens):
        _, *groups, _ = tokens
        return Charset(groups)

    def visit_charset_group(self, group):
        return group

    def visit_CHARSET_CHAR(self, token):
        ch = CHAR_ESCAPE.parse(token)
        return Char(ch)

    def visit_char_range(self, start, _, end):
        return CharRange(start, end)

    def visit_NUMBER(self, token):
        return int(token)


PARSER = Parser(EBNF_GRAMMAR, EbnfVisitor())


def parse_ebnf(text):
    (node,) = PARSER.first_full_parse(text)
    return node
