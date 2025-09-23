from attrs import field, frozen
from attrs.validators import (
    and_,
    deep_iterable,
    ge,
    instance_of,
    matches_re,
    max_len,
    min_len,
    optional,
)

__all__ = [
    "Expr",
    "Alt",
    "Cat",
    "Repeat",
    "Optional",
    "ZeroOrMore",
    "OneOrMore",
    "Symbol",
    "String",
    "Char",
    "CharRange",
    "Charset",
    "CharsetDiff",
    "Rule",
    "Grammar",
    "Visitor",
]


def to_string(x):
    return String(x) if isinstance(x, str) else x


def to_char(x):
    return Char(x) if isinstance(x, str) else x


def to_symbol(x):
    return Symbol(x) if isinstance(x, str) else x


@frozen
class Expr:
    pass


@frozen
class Alt(Expr):
    exprs: tuple[Expr, ...] = field(
        converter=tuple, validator=[min_len(2), deep_iterable(instance_of(Expr))]
    )

    @classmethod
    def create(cls, *exprs: Expr) -> Expr:
        exprs = (to_string(expr) for expr in exprs)
        # Expand nested Alts.
        exprs2 = []
        for expr in exprs:
            if isinstance(expr, Alt):
                exprs2.extend(expr.exprs)
            else:
                exprs2.append(expr)
        exprs = exprs2

        # Simplify if only one expr.
        if len(exprs) == 1:
            return exprs[0]

        return cls(exprs)


@frozen
class Cat(Expr):
    exprs: tuple[Expr, ...] = field(
        converter=tuple, validator=[min_len(2), deep_iterable(instance_of(Expr))]
    )

    @classmethod
    def create(cls, *exprs: Expr) -> Expr:
        exprs = (to_string(expr) for expr in exprs)
        # Expand nested Cats.
        exprs2 = []
        for expr in exprs:
            if isinstance(expr, Cat):
                exprs2.extend(expr.exprs)
            else:
                exprs2.append(expr)
        exprs = exprs2

        # Simplify if only one expr.
        if len(exprs) == 1:
            return exprs[0]

        return cls(exprs)


@frozen
class Repeat(Expr):
    expr: Expr = field(validator=instance_of(Expr))
    min: int = field(validator=[instance_of(int), ge(0)], default=0)
    max: int | None = field(
        validator=optional(and_(instance_of(int), ge(1))), default=None
    )

    def __attrs_post_init__(self):
        if self.max is not None and self.min > self.max:
            raise ValueError(f"{self.min} > {self.max}")

    @classmethod
    def create(cls, *exprs, min=0, max=None):
        expr = Cat.create(*exprs)
        if min == 0 and max is None:
            return ZeroOrMore(expr)
        if min == 0 and max == 1:
            return Optional(expr)
        if min == 1 and max is None:
            return OneOrMore(expr)
        return cls(expr, min, max)


@frozen
class Optional(Repeat):
    def __init__(self, expr: Expr):
        super().__init__(expr, 0, 1)

    @classmethod
    def create(cls, *exprs):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class ZeroOrMore(Repeat):
    def __init__(self, expr: Expr):
        super().__init__(expr, 0)

    @classmethod
    def create(cls, *exprs):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class OneOrMore(Repeat):
    def __init__(self, expr: Expr):
        super().__init__(expr, 1)

    @classmethod
    def create(cls, *exprs):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class Symbol(Expr):
    name: str = field(
        validator=[instance_of(str), matches_re("[a-zA-Z_][a-zA-Z0-9_]*")]
    )


@frozen
class String(Expr):
    value: str = field(validator=[instance_of(str), min_len(1)])


@frozen
class Char:
    char: str = field(validator=[instance_of(str), min_len(1), max_len(1)])


@frozen
class CharRange:
    start: Char = field(validator=instance_of(Char))
    end: Char = field(validator=instance_of(Char))

    def __attrs_post_init__(self):
        if self.start.char >= self.end.char:
            raise ValueError(f"Invalid range: {self.start}-{self.end}")

    @classmethod
    def create(cls, start: str | Char, end: str | Char) -> "CharRange":
        return cls(to_char(start), to_char(end))


@frozen
class Charset(Expr):
    groups: tuple[Char | CharRange, ...] = field(
        converter=tuple,
        validator=[deep_iterable(instance_of((Char, CharRange))), min_len(1)],
    )

    @classmethod
    def create(cls, *groups: str | Char | CharRange) -> "Charset":
        groups = (to_char(g) for g in groups)
        return cls(groups)


@frozen
class CharsetDiff(Expr):
    base: "Charset | Symbol | CharsetDiff" = field()
    diff: Charset | Symbol = field(validator=instance_of((Charset, Symbol)))

    @base.validator
    def _check_base(self, attribute, value):
        v = instance_of((Charset, Symbol, CharsetDiff))
        v(self, attribute, value)

    @classmethod
    def create(cls, base, *groups):
        if len(groups) == 0:
            return base
        if len(groups) == 1 and isinstance(groups[0], (Charset, Symbol)):
            return cls(base, groups[0])
        return cls(base, Charset.create(*groups))


@frozen
class Rule:
    name: Symbol = field(validator=instance_of(Symbol))
    expr: Expr = field(validator=instance_of(Expr))

    @classmethod
    def create(cls, name: str | Symbol, *exprs: Expr) -> "Rule":
        return cls(to_symbol(name), Cat.create(*exprs))


@frozen
class Grammar:
    rules: tuple[Rule, ...] = field(
        converter=tuple, validator=[min_len(1), deep_iterable(instance_of(Rule))]
    )

    _rule_map = field(factory=dict, init=False)

    def __attrs_post_init__(self):
        for rule in self.rules:
            if rule.name in self._rule_map:
                raise ValueError(f"Duplicate rule name: {rule.name}")
            self._rule_map[rule.name] = rule.expr

    @classmethod
    def create(cls, *rules, **kwargs) -> "Grammar":
        rules = list(rules)
        for k, v in kwargs.items():
            rules.append(Rule.create(k, v))
        return cls(rules)

    def get_rule(self, name: str) -> Rule:
        return self._rule_map[Symbol(name)]


class Visitor:
    def visit(self, name, *args):
        return (name,) + args
