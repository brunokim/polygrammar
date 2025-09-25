from polygrammar.grammars.lisp import parse_lisp
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

ABNF_GRAMMAR = parse_lisp(
    r'''
    (grammar
        (rule rulelist (| rule (cat (* WSP) c_nl)))
        (rule rule rulename defined_as elements c_nl)
        (rule rulename ALPHA (* (| ALPHA DIGIT "-")))
        (rule defined_as (* _c_wsp) (| "=" "=/") (* _c_wsp))
        (rule elements alternation (* WSP))
        (rule alternation
            concatenation
            (* (* _c_wsp) "/" (* _c_wsp) concatenation))
        (rule concatenation repetition (* (+ _c_wsp) repetition))
        (rule repetition (? repeat) element)
        (rule repeat (|
            (+ DIGIT)
            (cat (* DIGIT) "*" (* DIGIT))))
        (rule element (| rulename group option char_val num_val prose_val))
        (rule group "(" (* _c_wsp) alternation (* _c_wsp) ")")
        (rule option "[" (* _c_wsp) alternation (* _c_wsp) "]")
        (rule char_val (| case_sensitive_string case_insensitive_string))
        (rule case_sensitive_string "%s" quoted_string)
        (rule case_insensitive_string (? "%i") quoted_string)
        (rule quoted_string DQUOTE (* (| (- (charset (char_range " " "~")) DQUOTE))) DQUOTE)
        (rule num_val "%" (| bin_val dec_val hex_val))
        (rule bin_val "b"
            (+ BIT)
            (? (|
                (+ "." (+ BIT))
                (cat "-" (+ BIT)))))
        (rule dec_val "d"
            (+ DIGIT)
            (? (|
                (+ "." (+ DIGIT))
                (cat "-" (+ DIGIT)))))
        (rule hex_val "x"
            (+ HEXDIG)
            (? (|
                (+ "." (+ HEXDIG))
                (cat "-" (+ HEXDIG)))))
        (rule prose_val "<" (* (- (charset (char_range " " "~")) ">")) ">")

        ; Whitespace
        (rule _c_wsp (? c_nl) WSP)
        (rule c_nl (| comment CRLF))
        (rule comment ";" (* (| VCHAR WSP)) CRLF)

        ; ASCII character sets
        (rule WSP (charset " " "\t"))
        (rule BIT (charset "0" "1"))
        (rule DIGIT (charset (char_range "0" "9")))
        (rule HEXDIG (charset (char_range "0" "9") (char_range "A" "F")))
        (rule VCHAR (charset (char_range "!" "~")))
        (rule ALPHA (charset (char_range "A" "Z") (char_range "a" "z")))
        (rule CR "\r")
        (rule LF "\n")
        (rule CRLF "\r\n")
        (rule HTAB "\t")
        (rule SP " ")
        (rule DQUOTE """")
        (rule LWSP (* (| WSP (cat CRLF WSP))))
        (rule OCTET (charset (char_range "\x00" "\x7F")))
        (rule CHAR (charset (char_range "\x01" "\x7F")))
        (rule CTL (charset (char_range "\x00" "\x1F") "\x7F"))
    )
    '''
)


class AbnfVisitor(Visitor):
    pass


PARSER = Parser(ABNF_GRAMMAR, AbnfVisitor())


def parse_abnf(text: str) -> Grammar:
    (node,) = parser.first_full_parse(text)
    return node
