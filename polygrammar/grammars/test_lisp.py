from polygrammar.grammars.lisp import LISP_GRAMMAR, lisp_str, parse_lisp, to_lisp

LISP_GRAMMAR_STR = r'''
(grammar
  ; This is a generic Lisp-like grammar, allowing nested list expressions.
  ; The only terminals are symbols and strings.
  (rule terms _ (zero_or_more term _))
  (rule term "(" _ value (zero_or_more _1 value) _ ")")
  (rule value (alt SYMBOL STRING term))

  ; Symbol syntax inherits from C, which is the least-common denominator for most programming languages.
  (rule SYMBOL (alt letter "_") (zero_or_more (alt letter digit "_")))

  ; A string is a sequence of characters enclosed in double quotes.
  ; A double quote is escaped by doubling it. No other escapes are supported in this Lisp.
  ; """" -> " "" " -> a single double quote character
  ; """""" -> " "" "" " -> two double quote characters
  (rule STRING
    """"
    (zero_or_more
      (alt
        (charset_diff CHAR (charset """"))
        """"""))
    """")

  ; Whitespace
  (rule _ (zero_or_more (alt space comment)))
  (rule _1 (one_or_more (alt space comment)))
  (rule comment ";" (zero_or_more CHAR) "\n")

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
