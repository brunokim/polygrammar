from polygrammar.grammars.lisp import parse_catalog
from polygrammar.model import *
from polygrammar.recursive_parser import Parser

__all__ = ["parse_lark", "LARK_CATALOG"]

# Reference: https://github.com/lark-parser/lark/blob/master/lark/grammars/lark.lark
LARK_CATALOG = parse_catalog(
    r'''
    #(keep_literals false)
    (grammar
      (rule start (* (? _item) _NL) (? _item))
      (rule _item (alt rule token statement))

      (rule rule RULE rule_params (? priority) ":" expansions)
      (rule token TOKEN token_params (? priority) ":" expansions)
      (rule rule_params #maybe (? "{" RULE (* "," RULE) "}"))
      (rule token_params #maybe (? "{" TOKEN (* "," TOKEN) "}"))

      (rule priority "." NUMBER)

      (rule statement (alt
        #(name ignore)        (cat "%ignore" expansions)
        #(name import)        (cat "%import" import_path #maybe (? "->" name))
        #(name multi_import)  (cat "%import" import_path name_list)
        #(name override_rule) (cat "%override" rule)
        #(name declare)       (cat "%declare" (+ name))))

      #keep_literals
      (rule import_path (? ".") name (* "." name))

      (rule name_list "(" name (* "," name) ")")

      #inline_single
      (rule expansions alias (* _VBAR alias))

      #inline_single
      (rule alias expansion #maybe (? "->" RULE))

      #inline_single
      (rule expansion (* expr))

      #inline_single
      (rule expr atom #maybe (alt OP (cat "~" NUMBER #maybe (? ".." NUMBER))))

      #inline_single
      (rule atom (alt
        (cat "(" expansions ")")
        #(name maybe) (cat "[" expansions "]")
        value))

      #inline_single
      (rule value (alt
        #(name literal_range)  (cat STRING ".." STRING)
                               name
        #(name literal)        (alt REGEXP STRING)
        #(name template_usage) (cat name "{" value (* "," value) "}")))

      (rule name (alt RULE TOKEN))

      (rule _VBAR (? _NL) "|")
      (rule OP (regexp "[+*]|[?](?![a-z])"))
      (rule RULE (regexp "!?[_?]?[a-z][_a-z0-9]*"))
      (rule TOKEN (regexp "_?[A-Z][_A-Z0-9]*"))
      (rule STRING _STRING (? "i"))
      (rule REGEXP (regexp "/(?!/)(\\/|\\\\|[^/])*?/[imslux]*"))
      (rule _NL (regexp "(\r?\n)+\s*"))

      (directive import common ESCAPED_STRING _STRING)
      (directive import common SIGNED_INT NUMBER)
      (directive import common WS_INLINE)

      (rule COMMENT (alt
        (cat (regexp "\s*") "//" (* (regexp "[^\n]")))
        (cat (regexp "\s*") "#" (regexp "[^\n]"))))

      (directive ignore WS_INLINE)
      (directive ignore COMMENT)
    )

    #(name common)
    (grammar
      ;
      ; Numbers
      ;

      (rule DIGIT (charset (char_range "0" "9")))
      (rule HEXDIGIT (alt
        (charset (char_range "a" "f"))
        (charset (char_range "A" "F"))
        DIGIT))

      (rule SIGN (charset "+" "-"))

      (rule INT (+ DIGIT))
      (rule SIGNED_INT #maybe (? SIGN) INT)
      (rule DECIMAL (alt
        (cat INT "." (? INT))
        (cat "." INT)))

      (rule _EXP #i "e" SIGNED_INT)
      (rule FLOAT (alt (cat INT _EXP) (cat DECIMAL (? _EXP))))
      (rule SIGNED_FLOAT #maybe (? SIGN) FLOAT)

      (rule NUMBER (alt FLOAT INT))
      (rule SIGNED_NUMBER #maybe (? SIGN) NUMBER)

      ;
      ; Strings
      ;

      (rule _STRING_INNER (regexp ".*?"))
      (rule _STRING_ESC_INNER _STRING_INNER (regexp "(?<!\\\\)(\\\\\\\\)*?"))

      (rule ESCAPED_STRING """" _STRING_ESC_INNER """")

      ;
      ; Names (Variables)
      ;

      (rule LCASE_LETTER (charset (char_range "a" "z")))
      (rule UCASE_LETTER (charset (char_range "A" "Z")))
      (rule LETTER (alt UCASE_LETTER LCASE_LETTER))
      (rule WORD (+ LETTER))

      (rule CNAME (alt "_" LETTER) (* (alt "_" LETTER DIGIT)))

      ;
      ; Whitespace
      ;

      (rule WS_INLINE (+ (alt " " (regexp "\t"))))
      (rule WS (+ (regexp " \t\f\r\n")))

      (rule CR (regexp "\r"))
      (rule LF (regexp "\n"))
      (rule NEWLINE (+ (? CR) LF))

      ; Comments
      (rule SH_COMMENT  (regexp "#[^\n]*"))
      (rule CPP_COMMENT (regexp "//[^\n]*"))
      (rule SQL_COMMENT (regexp "--[^\n]*"))
      (rule C_COMMENT   "/*" (regexp "(.|\n)*?") "*/")
    )
    '''
)


class LarkVisitor(Visitor):
    def visit_start(self, *rules):
        return Grammar(rules)

    def visit_rule(self, *args):
        match args:
            case [name, None, expansions]:
                return Rule(name, expansions)
            case _:
                raise NotImplementedError(f"{args}")

    def visit_REGEXP(self, token):
        start = 1
        assert token[:start] == "/"
        end = token.rfind("/")
        pattern = token[start:end]
        flags = token[end + 1 :]
        if flags:
            pattern = f"(?{flags}:{pattern})"
        return Regexp(pattern)


PARSER = Parser.from_grammar(LARK_CATALOG[0], LarkVisitor(), catalog=LARK_CATALOG)


def parse_lark(text):
    tree, _ = PARSER.first_parse(text)
    (grammar,) = tree
    return grammar
