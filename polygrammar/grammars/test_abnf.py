from polygrammar.grammars.abnf import ABNF_GRAMMAR
from polygrammar.grammars.ebnf import to_ebnf

print(to_ebnf(ABNF_GRAMMAR))
