from polygrammar.grammars.lisp import LISP_GRAMMAR, lisp_str, parse_lisp, to_lisp

LISP_GRAMMAR_STR = r'''
(grammar
  ; This is a generic Lisp-like grammar, allowing nested list expressions.
  ; The only terminals are symbols and strings.
  (rule terms _ (* term _))
  (rule term "(" _ value (* _1 value) _ ")")
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


def test_parse_lisp():
    grammar = parse_lisp(LISP_GRAMMAR_STR)
    assert grammar == LISP_GRAMMAR


def test_self_parse():
    data = to_lisp(LISP_GRAMMAR)
    text = lisp_str(data)
    g = parse_lisp(text)
    assert g == LISP_GRAMMAR
