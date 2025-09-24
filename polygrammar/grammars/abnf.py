from polygrammar.grammars.lisp import parse_lisp
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

ABNF_GRAMMAR = parse_lisp(
    r'''
    (grammar
        (rule rulelist (alt rule (cat (zero_or_more WSP) c_nl)))
        (rule rule rulename defined_as elements c_nl)
        (rule rulename ALPHA (zero_or_more (alt ALPHA DIGIT "-")))
        (rule defined_as (zero_or_more _c_wsp) (alt "=" "=/") (zero_or_more _c_wsp))
        (rule elements alternation (zero_or_more WSP))
        (rule alternation
            concatenation
            (zero_or_more (zero_or_more _c_wsp) "/" (zero_or_more _c_wsp) concatenation))
        (rule concatenation repetition (zero_or_more (one_or_more _c_wsp) repetition))
        (rule repetition (optional repeat) element)
        (rule repeat (alt
            (one_or_more DIGIT)
            (cat (zero_or_more DIGIT) "*" (zero_or_more DIGIT))))
        (rule element (alt rulename group option char_val num_val prose_val))
        (rule group "(" (zero_or_more _c_wsp) alternation (zero_or_more _c_wsp) ")")
        (rule option "[" (zero_or_more _c_wsp) alternation (zero_or_more _c_wsp) "]")
        (rule char_val (alt case_sensitive_string case_insensitive_string))
        (rule case_sensitive_string "%s" quoted_string)
        (rule case_insensitive_string (optional "%i") quoted_string)
        (rule quoted_string DQUOTE (zero_or_more (alt (diff (charset (char_range " " "~")) DQUOTE))) DQUOTE)
        (rule num_val "%" (alt bin_val dec_val hex_val))
        (rule bin_val "b"
            (one_or_more BIT)
            (optional (alt
                (one_or_more "." (one_or_more BIT))
                (cat "-" (one_or_more BIT)))))
        (rule dec_val "d"
            (one_or_more DIGIT)
            (optional (alt
                (one_or_more "." (one_or_more DIGIT))
                (cat "-" (one_or_more DIGIT)))))
        (rule hex_val "x"
            (one_or_more HEXDIG)
            (optional (alt
                (one_or_more "." (one_or_more HEXDIG))
                (cat "-" (one_or_more HEXDIG)))))
        (rule prose_val "<" (zero_or_more (diff (charset (char_range " " "~")) ">")) ">")

        ; Whitespace
        (rule _c_wsp (optional c_nl) WSP)
        (rule c_nl (alt comment CRLF))
        (rule comment ";" (zero_or_more (alt VCHAR WSP)) CRLF)

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
        (rule LWSP (zero_or_more (alt WSP (cat CRLF WSP))))
        ; (rule OCTET (charset (char_range "\x00" "\x7F")))
        ; (rule CHAR (charset (char_range "\x01" "\x7F")))
        ; (rule CTL (charset (char_range "\x00" "\x1F") "\x7F"))
    )
    '''
)


class AbnfVisitor(Visitor):
    pass


PARSER = Parser(ABNF_GRAMMAR, AbnfVisitor())


def parse_abnf(text: str) -> Grammar:
    (node,) = parser.first_full_parse(text)
    return node
