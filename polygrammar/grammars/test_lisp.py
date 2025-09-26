from textwrap import dedent

import pytest

from polygrammar.grammars.lisp import (
    LISP_GRAMMAR,
    lisp_str,
    parse_lisp_data,
    parse_lisp_grammar,
    to_lisp,
)
from polygrammar.model import Symbol

LISP_GRAMMAR_STR = r'''
(grammar
  ; This is a generic Lisp-like grammar, allowing nested list expressions.
  ; The only terminals are symbols and strings.
  (rule values _ (* annotated_value _))
  (rule term "(" _ (? annotated_value (* _1 annotated_value) _) ")")
  (rule annotated_value (* "#" value _) value)
  (rule value (| SYMBOL STRING term))

  ; Symbol syntax inherits from C, which is the least-common denominator for most programming languages.
  (rule SYMBOL (| c_symbol operator))
  (rule c_symbol
    (| letter "_")
    (* (| letter digit "_" "-")))
  (rule operator (charset "+" "*" "?" "/" "|" "-" "!"))

  ; A string is a sequence of characters enclosed in double quotes.
  ; A double quote is escaped by doubling it.
  ; """" -> " "" " -> a single double quote character
  ; """""" -> " "" "" " -> two double quote characters
  (rule STRING
    """"
    (* (|
      (charset_diff CHAR """" "\\")
      """"""
      (cat "\\" CHAR)))
    """")

  ; Whitespace
  (rule _ (* (| space comment)))
  (rule _1 (+ (| space comment)))
  (rule comment ";" (* CHAR) "\n")

  ; ASCII character classes
  (rule letter (charset (char_range "a" "z") (char_range "A" "Z")))
  (rule digit (charset (char_range "0" "9")))
  (rule space (charset " " "\t" "\n" "\r" ","))
  (rule CHAR (charset (char_range "!" "~") " " "\t")))
'''


@pytest.mark.parametrize(
    "text, data",
    [
        ("()", ()),
        ('"abc"', "abc"),
        ("abc", Symbol("abc")),
        ("()", ()),
        ("(a b c)", (Symbol("a"), Symbol("b"), Symbol("c"))),
        (
            dedent(
                """\
                ("long"
                  "long"
                  ("long"
                    "long"
                    "long"
                    "long"
                    "long"
                    ("long" "long" "long" "long" "long" "long")
                    "long"
                    "long"
                    "long"
                    "long")
                  "long"
                  "long"
                  "args"
                  "list")"""
            ),
            (
                "long",
                "long",
                (
                    "long",
                    "long",
                    "long",
                    "long",
                    "long",
                    ("long", "long", "long", "long", "long", "long"),
                    "long",
                    "long",
                    "long",
                    "long",
                ),
                "long",
                "long",
                "args",
                "list",
            ),
        ),
    ],
)
def test_parse_lisp_data(text, data):
    assert parse_lisp_data(text) == data
    assert lisp_str(data) == text


def test_parse_lisp_grammar():
    grammar = parse_lisp_grammar(LISP_GRAMMAR_STR)
    assert grammar == LISP_GRAMMAR


def test_self_parse():
    data = to_lisp(LISP_GRAMMAR)
    text = lisp_str(data)
    g = parse_lisp_grammar(text)
    assert g == LISP_GRAMMAR
