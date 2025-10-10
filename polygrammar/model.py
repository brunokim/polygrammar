from collections.abc import Mapping

from attrs import field, frozen
from attrs.validators import (
    and_,
    deep_iterable,
    ge,
    instance_of,
    max_len,
    min_len,
    optional,
)

__all__ = [
    "Node",
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
    "EndOfFile",
    "CharRange",
    "Charset",
    "Diff",
    "CharsetDiff",
    "Rule",
    "Grammar",
    "Visitor",
]


def to_string(x):
    return String(x) if isinstance(x, str) else x


def to_char(x):
    return Char(x) if isinstance(x, str) else x


def to_charset(x):
    return Charset([x]) if isinstance(x, (Char, CharRange)) else x


def to_symbol(x):
    return Symbol(x) if isinstance(x, str) else x


@frozen
class Node:
    @property
    def children(self):
        return ()

    @property
    def attributes(self):
        return {}


@frozen
class Expr(Node):
    __meta__: list = field(init=False, eq=False, hash=False, repr=False, factory=list)

    @property
    def metadata(self):
        d = {}
        for x in self.__meta__:
            match x:
                case [k, v]:
                    d[k] = v
                case Mapping():
                    d.update(x)
                case _:
                    d[x] = True
        return d

    def has_meta(self, *names):
        meta = self.metadata
        return any(Symbol(name) in meta for name in names)

    def get_meta(self, name, default=None):
        return self.metadata.get(Symbol(name), default)


@frozen
class Alt(Expr):
    exprs: tuple[Expr, ...] = field(
        converter=tuple, validator=[min_len(2), deep_iterable(instance_of(Expr))]
    )

    @property
    def children(self):
        return self.exprs

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

    @property
    def children(self):
        return self.exprs

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
        validator=optional(and_(instance_of(int), ge(0))), default=None
    )

    def __attrs_post_init__(self):
        if self.max is not None and self.min > self.max:
            raise ValueError(f"{self.min} > {self.max}")

    @property
    def children(self):
        return (self.expr,)

    @property
    def attributes(self):
        return {"min": self.min, "max": self.max}

    @classmethod
    def create(cls, *exprs: Expr, min=0, max=None):
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
    def create(cls, *exprs: Expr):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class ZeroOrMore(Repeat):
    def __init__(self, expr: Expr):
        super().__init__(expr, 0)

    @classmethod
    def create(cls, *exprs: Expr):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class OneOrMore(Repeat):
    def __init__(self, expr: Expr):
        super().__init__(expr, 1)

    @classmethod
    def create(cls, *exprs: Expr):
        expr = Cat.create(*exprs)
        return cls(expr)


@frozen
class Symbol(Expr):
    name: str = field(validator=[instance_of(str), min_len(1)])


@frozen
class String(Expr):
    value: str = field(validator=[instance_of(str), min_len(1)])


class EndOfFile(Expr):
    pass


@frozen
class Char(Node):
    char: str = field(validator=[instance_of(str), min_len(1), max_len(1)])


@frozen
class CharRange(Node):
    start: Char = field(validator=instance_of(Char))
    end: Char = field(validator=instance_of(Char))

    def __attrs_post_init__(self):
        if self.start.char >= self.end.char:
            raise ValueError(f"Invalid range: {self.start}-{self.end}")

    @property
    def children(self):
        return (self.start, self.end)

    @classmethod
    def create(cls, start: str | Char, end: str | Char) -> "CharRange":
        return cls(to_char(start), to_char(end))


@frozen
class Charset(Expr):
    groups: tuple[Char | CharRange, ...] = field(
        converter=tuple,
        validator=[deep_iterable(instance_of((Char, CharRange))), min_len(1)],
    )

    @property
    def children(self):
        return self.groups

    @classmethod
    def create(cls, *groups: str | Char | CharRange) -> "Charset":
        groups = (to_char(g) for g in groups)
        return cls(groups)


@frozen
class Diff(Expr):
    base: Expr = field(validator=instance_of(Expr))
    diff: Expr = field(validator=instance_of(Expr))

    @property
    def children(self):
        return (self.base, self.diff)

    @classmethod
    def create(cls, base: Expr, *exprs: Expr) -> "Diff":
        for expr in exprs:
            base = cls(base, to_string(expr))
        return base


@frozen
class CharsetDiff(Diff):
    def __attrs_post_init__(self):
        if not isinstance(self.base, (Charset, Symbol, CharsetDiff)):
            raise TypeError(
                f"base must be Charset, Symbol, or CharsetDiff got {type(self.base)}"
            )
        if not isinstance(self.diff, (Charset, Symbol)):
            raise TypeError(f"diff must be Charset or Symbol, got {type(self.diff)}")

    @classmethod
    def create(cls, base: Expr, *exprs: Expr) -> "CharsetDiff":
        for expr in exprs:
            base = cls(base, to_charset(to_char(expr)))
        return base


@frozen
class Rule(Node):
    name: Symbol = field(validator=instance_of(Symbol))
    expr: Expr = field(validator=instance_of(Expr))

    is_additional_cat: bool = field(default=False, validator=instance_of(bool))
    is_additional_alt: bool = field(default=False, validator=instance_of(bool))

    @property
    def children(self):
        return (self.name, self.expr)

    @property
    def attributes(self):
        return {
            "is_additional_cat": self.is_additional_cat,
            "is_additional_alt": self.is_additional_alt,
        }

    @classmethod
    def create(
        cls,
        name: str | Symbol,
        *exprs: Expr,
        is_additional_cat=False,
        is_additional_alt=False,
    ) -> "Rule":
        return cls(
            to_symbol(name), Cat.create(*exprs), is_additional_cat, is_additional_alt
        )


@frozen
class Grammar(Node):
    rules: tuple[Rule, ...] = field(
        converter=tuple, validator=[min_len(1), deep_iterable(instance_of(Rule))]
    )

    @property
    def children(self):
        return self.rules

    @classmethod
    def create(cls, *rules, **kwargs) -> "Grammar":
        rules = list(rules)
        for k, v in kwargs.items():
            rules.append(Rule.create(k, v))
        return cls(rules)


# Recursive walk


def walk(node, f):
    for child in node.children:
        yield from walk(child, f)
    yield from f(node)


def transform(node, f):
    if not node.children:
        return f(node)
    cls = type(node)
    children = (transform(c, f) for c in node.children)
    return cls.create(*children, **node.attributes)


def symbols(e: Expr):
    def f(e):
        if isinstance(e, Symbol):
            yield e.name

    return set(walk(e, f))


# Visitor


class Visitor:
    def visit(self, name, *args):
        return (name,) + args
