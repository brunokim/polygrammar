from hypothesis import strategies as st
from multimethod import multimethod

from polygrammar.model import *
from polygrammar.recursive_parser import ParseError, Parser


@multimethod
def generator(self: Charset, gen_map, parser):
    char_generators = [generator(group, gen_map, parser) for group in self.groups]
    return st.one_of(char_generators)


@multimethod
def generator(self: Char, gen_map, parser):
    return st.just(self.char)


@multimethod
def generator(self: CharRange, gen_map, parser):
    return st.characters(
        min_codepoint=ord(self.start.char),
        max_codepoint=ord(self.end.char),
    )


@multimethod
def generator(self: Cat, gen_map, parser):
    sub_generators = [generator(expr, gen_map, parser) for expr in self.exprs]

    @st.composite
    def f(draw):
        return "".join(draw(g) for g in sub_generators)

    return f()


@multimethod
def generator(self: Alt, gen_map, parser):
    generators = [generator(expr, gen_map, parser) for expr in self.exprs]
    return st.one_of(generators)


@multimethod
def generator(self: Repeat, gen_map, parser):
    g = st.lists(
        generator(self.expr, gen_map, parser),
        min_size=self.min,
        max_size=min(self.max or 3, 3),
    )

    @st.composite
    def f(draw):
        return "".join(draw(g))

    return f()


@multimethod
def generator(self: Optional, gen_map, parser):
    return generator(Repeat(self.expr, min=0, max=1), gen_map, parser)


@multimethod
def generator(self: ZeroOrMore, gen_map, parser):
    return generator(Repeat(self.expr, min=0, max=None), gen_map, parser)


@multimethod
def generator(self: OneOrMore, gen_map, parser):
    return generator(Repeat(self.expr, min=1, max=None), gen_map, parser)


@multimethod
def generator(self: Symbol, gen_map, parser):
    return st.deferred(lambda: gen_map[self])


@multimethod
def generator(self: String, gen_map, parser):
    return st.just(self.value)


@multimethod
def generator(self: Empty, gen_map, parser):
    return st.just("")


@multimethod
def generator(self: Regexp, gen_map, parser):
    return st.from_regex(self.pattern)


@multimethod
def generator(self: Diff, gen_map, parser):
    gen_base = generator(self.base, gen_map, parser)

    @st.composite
    def f(draw):
        while True:
            value = draw(gen_base)
            try:
                parser.first_parse(value, self.diff, debug=False)
                continue
            except ParseError:
                return value

    return f()


@multimethod
def generator(self: Grammar, expr=None):
    parser = Parser.from_grammar(self)

    if expr is None:
        expr = self.rules[0].name
    gen_map = {}
    for rule in self.rules:
        gen_map[rule.name] = generator(rule.expr, gen_map, parser)

    return generator(expr, gen_map, parser)


if __name__ == "__main__":
    import warnings

    from hypothesis.errors import NonInteractiveExampleWarning

    warnings.simplefilter("ignore", NonInteractiveExampleWarning)

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
    g = generator(EBNF_GRAMMAR, Symbol("expr"))
    for _ in range(10):
        print(g.example())
