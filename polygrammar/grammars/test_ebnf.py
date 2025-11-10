import re

from hypothesis import Phase, assume, given, settings

from polygrammar.generate import generator
from polygrammar.grammars.ebnf import EBNF_GRAMMAR, parse_ebnf, to_ebnf

EBNF_GRAMMAR_STR = r"""
grammar = _ (rule _ ';' _)+ ;
rule    = SYMBOL _ '=' _ expr ;

# Expressions
expr    = alt ;
alt     = cat (_ '|' _ cat)* ;
cat     = term (_1 term)* ;
term    = repeat | diff | atom ;
repeat  = atom ('*' | '+' | '?' | min_max) ;
min_max = '{' NUMBER? ',' NUMBER? '}' ;
diff    = atom (_ '-' _ atom)+ ;
atom    = SYMBOL | STRING | charset | '(' _ expr _ ')' ;

# Symbol uses C syntax.
SYMBOL = (letter | '_') (letter | digit | '_')* ;

# String may use double or single quotes. Escape a quote by doubling it or with backslash.
STRING        = dquote_string | squote_string ;
dquote_string = '"' (CHAR - '"' - '\\' | '""' | '\\' CHAR)* '"' ;
squote_string = "'" (CHAR - "'" - "\\" | "''" | '\\' CHAR)* "'" ;

/* Charset use a limited regex syntax.
   - "^" for negation is not supported; use a diff '-' instead.
   - "-" always needs to be escaped, independent of its position.
*/
charset       = '[' charset_group+ ']' ;
charset_group = char_range | CHARSET_CHAR ;
CHARSET_CHAR  = CHAR - ']' - '-' - '\\' | '\\' CHAR ;
char_range    = CHARSET_CHAR '-' CHARSET_CHAR ;

# Number is a sequence of digits.
NUMBER = digit+ ;

# Whitespace
_             = (space | comment)* ;
_1            = (space | comment)+ ;
comment       = line_comment | block_comment ;
line_comment  = '#' CHAR* '\n' ;
block_comment = '/*' (CHAR1 - '*' | '*' (CHAR1 - '/'))* '*'? '*/' ;

# ASCII character classes
letter = [a-zA-Z] ;
digit  = [0-9] ;
space  = [ \t\n\r] ;
CHAR   = [!-~ \t] ;
CHAR1  = [!-~ \t\n\r] ;
"""


def test_parse_ebnf():
    parsed = parse_ebnf(EBNF_GRAMMAR_STR)
    assert parsed == EBNF_GRAMMAR


def test_self_parse():
    ebnf = to_ebnf(EBNF_GRAMMAR)
    parsed = parse_ebnf(ebnf)
    assert parsed == EBNF_GRAMMAR


@given(generator(EBNF_GRAMMAR))
@settings(deadline=None, phases=[Phase.generate])
def test_ebnf_generate(text):
    try:
        parse_ebnf(text)
    except ValueError as e:
        # Generated a char range with invalid endpoints.
        m = re.match(
            r"^Invalid range: Char\(char='([^']+)'\)-Char\(char='([^']+)'\)$", str(e)
        )
        # Mark example as bad.
        assume(not m)
