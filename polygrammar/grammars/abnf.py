from attrs import evolve

from polygrammar.grammars.lisp import parse_lisp_grammar
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

STRICT_ABNF_GRAMMAR = parse_lisp_grammar(
    r'''
    (grammar
        ; Rules
        (rule rulelist (+ (| rule #_(cat (* WSP) c-nl))))
        (rule rule rulename defined-as elements c-nl)
        (rule rulename ALPHA (* (| ALPHA DIGIT "-")))
        (rule defined-as #_(* c-wsp) (| "=" "=/") #_(* c-wsp))

        ; Expressions
        (rule elements alternation #_(* WSP))
        (rule alternation
            concatenation
            (* #_(* c-wsp) "/" #_(* c-wsp) concatenation))
        (rule concatenation repetition (* #_(+ c-wsp) repetition))
        (rule repetition (? repeat) element)
        (rule repeat (|
            (+ DIGIT)
            (cat (* DIGIT) "*" (* DIGIT))))
        (rule element (| rulename group option char-val num-val prose-val))
        (rule group "(" #_(* c-wsp) alternation #_(* c-wsp) ")")
        (rule option "[" #_(* c-wsp) alternation #_(* c-wsp) "]")

        ; Strings
        (rule char-val (| case-sensitive-string case-insensitive-string))
        (rule case-sensitive-string "%s" #token quoted-string)
        (rule case-insensitive-string (? "%i") #token quoted-string)
        (rule quoted-string DQUOTE (* (| (- (charset (char_range " " "~")) DQUOTE))) DQUOTE)

        ; Numeric values.
        (rule num-val "%" (| bin-val dec-val hex-val))
        (rule bin-val "b"
            (+ BIT)
            (? (|
                (+ "." (+ BIT))
                (cat "-" (+ BIT)))))
        (rule dec-val "d"
            (+ DIGIT)
            (? (|
                (+ "." (+ DIGIT))
                (cat "-" (+ DIGIT)))))
        (rule hex-val "x"
            (+ HEXDIG)
            (? (|
                (+ "." (+ HEXDIG))
                (cat "-" (+ HEXDIG)))))

        ; Prose placeholder.
        (rule prose-val "<" (* (- (charset (char_range " " "~")) ">")) ">")

        ; Whitespace
        (rule c-wsp (? c-nl) WSP)
        (rule c-nl (| comment nl))
        (rule nl CRLF)
        (rule comment ";" (* (| VCHAR WSP)) nl)

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
    def visit_rulelist(self, *args):
        return Grammar(args)

    def visit_rule(self, *args):
        name, defined_as, elements, _ = args
        rule = Rule(name, elements)
        if defined_as == "=/":
            rule = evolve(rule, is_additional_alt=True)
        return rule

    def visit_rulename(self, *tokens):
        return Symbol("".join(tokens))

    def visit_defined_as(self, token):
        return token

    def visit_elements(self, arg):
        return arg

    def visit_alternation(self, *args):
        return Alt.create(*(args[i] for i in range(0, len(args), 2)))

    def visit_concatenation(self, *args):
        return Cat.create(*args)

    def visit_repetition(self, *args):
        if len(args) == 1:
            return args[0]
        (_, *chars), element = args
        chars = iter(chars)

        ch = next(chars)

        def read_num():
            nonlocal ch
            num = ""
            while ch is not None and ch.isdigit():
                num += ch
                ch = next(chars, None)
            return int(num)

        if ch == "*":
            ch = next(chars, None)
            if ch is None:
                # Case *expr
                return ZeroOrMore.create(element)
            max = read_num()
            # Case *2expr
            return Repeat.create(element, min=0, max=max)

        min = read_num()

        if ch is None:
            # Case 2expr
            return Repeat.create(element, min=min, max=min)
        assert ch == "*"

        ch = next(chars, None)
        if ch is None:
            # Case 2*expr
            return Repeat.create(element, min=min)

        max = read_num()
        # Case 2*3expr
        return Repeat.create(element, min=min, max=max)

    def visit_element(self, arg):
        return arg

    def visit_group(self, *args):
        _, arg, _ = args
        return arg

    def visit_option(self, *args):
        _, arg, _ = args
        return Optional(arg)

    def visit_char_val(self, arg):
        return arg

    def visit_case_sensitive_string(self, *args):
        _, arg = args
        arg = String(arg)
        arg.__meta__.append(("case_sensitive", True))
        return arg

    def visit_case_insensitive_string(self, *args):
        arg = String(args[-1])
        arg.__meta__.append(("case_sensitive", False))
        return arg

    def visit_quoted_string(self, token):
        return token[1:-1]

    def visit_num_val(self, _, arg):
        return arg

    def visit_bin_val(self, _, *args):
        return self._visit_num_val(args, 2)

    def visit_dec_val(self, _, *args):
        return self._visit_num_val(args, 10)

    def visit_hex_val(self, _, *args):
        return self._visit_num_val(args, 16)

    def _visit_num_val(self, args, base):
        args = iter(args)

        chars = []
        sep = ""

        num = ""
        ch = next(args)
        while True:
            num += ch
            ch = next(args, None)
            if ch is None:
                chars.append(chr(int(num, base)))
                break
            if ch in ".-":
                chars.append(chr(int(num, base)))
                sep = ch
                num = ""
                ch = next(args, None)

        if sep in {".", ""}:
            return String("".join(chars))

        assert sep == "-"
        assert len(chars) == 2
        return Charset.create(CharRange.create(chars[0], chars[1]))

    def visit_prose_val(self, *chars):
        return String("".join(chars[1:-1]))


# Allow LF and EOF as a newline, in addition to CRLF.
ABNF_GRAMMAR = evolve(
    STRICT_ABNF_GRAMMAR,
    rules=STRICT_ABNF_GRAMMAR.rules
    + (
        Rule.create(
            "nl", Alt.create(String("\n"), EndOfFile()), is_additional_alt=True
        ),
    ),
)

STRICT_PARSER = Parser(STRICT_ABNF_GRAMMAR, AbnfVisitor())
PARSER = Parser(ABNF_GRAMMAR, AbnfVisitor())


def parse_abnf(text: str, strict_newlines=False):
    parser = STRICT_PARSER if strict_newlines else PARSER
    (node,) = parser.first_full_parse(text)
    return node
