from hypothesis import strategies as st
from multimethod import multimethod

from polygrammar.model import *


@multimethod
def generator(self: Charset, gen_map):
    char_generators = [generator(group, gen_map) for group in self.groups]
    return st.one_of(char_generators)


@multimethod
def generator(self: Char, gen_map):
    return st.just(self.char)


@multimethod
def generator(self: CharRange, gen_map):
    return st.characters(
        min_codepoint=ord(self.start.char),
        max_codepoint=ord(self.end.char),
    )


@multimethod
def generator(self: Cat, gen_map):
    sub_generators = [generator(expr, gen_map) for expr in self.exprs]

    @st.composite
    def f(draw):
        return "".join(draw(g) for g in sub_generators)

    return f()


@multimethod
def generator(self: Alt, gen_map):
    generators = [generator(expr, gen_map) for expr in self.exprs]
    return st.one_of(generators)


@multimethod
def generator(self: Repeat, gen_map):
    g = st.lists(generator(self.expr, gen_map), min_size=self.min, max_size=self.max)

    @st.composite
    def f(draw):
        return "".join(draw(g))

    return f()


@multimethod
def generator(self: Optional, gen_map):
    return generator(Repeat(self.expr, min=0, max=1), gen_map)


@multimethod
def generator(self: ZeroOrMore, gen_map):
    return generator(Repeat(self.expr, min=0, max=None), gen_map)


@multimethod
def generator(self: OneOrMore, gen_map):
    return generator(Repeat(self.expr, min=1, max=None), gen_map)


@multimethod
def generator(self: Symbol, gen_map):
    return st.deferred(lambda: gen_map[self])


@multimethod
def generator(self: String, gen_map):
    return st.just(self.value)


@multimethod
def generator(self: Empty, gen_map):
    return st.just("")


@multimethod
def generator(self: Regexp, gen_map):
    return st.from_regex(self.pattern)


@multimethod
def generator(self: Diff, gen_map):
    # TODO: execute diff
    return generator(self.base, gen_map)


@multimethod
def generator(self: Grammar, expr=None):
    if expr is None:
        expr = self.rules[0].name
    gen_map = {}
    for rule in self.rules:
        gen_map[rule.name] = generator(rule.expr, gen_map)
    return generator(expr, gen_map)


if __name__ == "__main__":
    grammar = Grammar.create(
        symbol=Cat.create(Symbol("first_char"), ZeroOrMore(Symbol("other_char"))),
        first_char=Alt.create(Symbol("lower"), Symbol("upper")),
        other_char=Alt.create(Symbol("lower"), Symbol("upper"), Symbol("digit")),
        lower=Charset.create(CharRange.create("a", "z")),
        upper=Charset.create(CharRange.create("A", "Z")),
        digit=Charset.create(CharRange.create("0", "9")),
    )

    print("== symbols ==")
    g = generator(grammar)
    for _ in range(10):
        print(g.example())

    from polygrammar.grammars.ebnf import EBNF_GRAMMAR

    print("== EBNF ==")
    g = generator(EBNF_GRAMMAR, Symbol("STRING"))
    for _ in range(10):
        print(g.example())
