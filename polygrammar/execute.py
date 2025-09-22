from collections import defaultdict
from textwrap import dedent
from typing import Any

from attrs import define, field, frozen, evolve
from attrs.validators import instance_of, optional, deep_iterable

from myopic.model import (
    Grammar,
    Alt,
    Cat,
    Repeat,
    Symbol,
    String,
    Charset,
    CharsetDiff,
    Char,
    CharRange,
    Repeat,
    Visitor,
)


__all__ = ["Parser", "ParseError"]


def optimize_alt(alt):
    # Transform Alt to Charset, if possible.
    chars, exprs2 = [], []
    for expr in alt.exprs:
        if isinstance(expr, String) and len(expr.value) == 1:
            chars.append(Char(expr.value))
        elif isinstance(expr, Charset):
            chars.extend(expr.groups)
        else:
            exprs2.append(expr)
    if len(chars) > 1:
        exprs = [Charset(chars)] + exprs2


def optimize_charset(charset):
    # Merge ranges and chars.
    ranges = []
    for g in charset.groups:
        if isinstance(g, CharRange):
            ranges.append((g.start.char, g.end.char))
        elif isinstance(g, Char):
            ranges.append((g.char, g.char))
    ranges.sort()
    merged = []
    for start, end in ranges:
        if not merged:
            merged.append((start, end))
            continue
        last_start, last_end = merged[-1]
        if ord(start) <= ord(last_end) + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    groups = []
    for start, end in merged:
        if start == end:
            groups.append(Char(start))
        elif ord(start) + 1 == ord(end):
            groups.append(Char(start))
            groups.append(Char(end))
        else:
            groups.append(CharRange(Char(start), Char(end)))


@define
class ParseError(Exception):
    text: str
    offset: int
    msg: str
    msg_args: tuple = field(default=())

    def __str__(self):
        line_start = 0
        line_number = 1

        for i, ch in enumerate(self.text):
            if ch == "\n":
                line_start = i + 1
                line_number += 1
            if i == self.offset:
                break

        line_end = self.text.find("\n", self.offset)
        line_end = line_end if line_end != -1 else len(self.text)

        line = self.text[line_start:line_end]
        col = self.offset - line_start
        pointer = " " * col + "^"
        msg = self.msg.format(*self.msg_args)
        return dedent(
            f"""\
            At {line_number}:{col+1} ({self.offset}): {msg}
                {line}
                {pointer}
            """
        )


@frozen
class Parser:
    grammar: Grammar = field(validator=instance_of(Grammar))
    visitor: Visitor = field(factory=Visitor)

    _method_map: dict = field(init=False, factory=dict)

    def __attrs_post_init__(self):
        for rule in self.grammar.rules:
            method_name = f"visit_{rule.name.name}"
            if hasattr(self.visitor, method_name):
                self._method_map[rule.name.name] = getattr(self.visitor, method_name)

    def parse(self, text, start=None, offset=0):
        if start is None:
            start = self.grammar.rules[0].name.name
        job = ParseJob(self, text)
        yield from job.parse(start, offset)

    def full_parse(self, text, start=None):
        for result, offset in self.parse(text, start):
            if offset != len(text):
                yield ParseError(text, offset, "trailing characters")
            else:
                yield result

    def first_parse(self, text, start=None, offset=0):
        try:
            result = next(self.parse(text, start, offset))
            if isinstance(result, ParseError):
                raise result
            return result
        except StopIteration:
            raise ParseError(text, offset, "no match")

    def first_full_parse(self, text, start=None):
        try:
            result = next(self.full_parse(text, start))
            if isinstance(result, ParseError):
                raise result
            return result
        except StopIteration:
            raise ParseError(text, 0, "no match")


@define
class State:
    offset: int = field(validator=instance_of(int), default=0)
    results: list[Any] = field(factory=list)
    blocked = field()


@frozen
class ParseJob:
    parser: Parser = field(validator=instance_of(Parser))
    text: str = field(validator=instance_of(str))

    _table: dict = field(init=False, factory=dict)
    _blocked: dict = field(init=False, factory=lambda: defaultdict(list))

    def parse(self, start, offset):
        initial_state = State(offset=offset)
        for state in self._parse_symbol(initial_state, start):
            yield state.results, state.offset

    def _error(self, msg, offset, *args, cause=None):
        error = ParseError(self.text, offset, msg, args)
        error.__cause__ = cause
        return error

    def _parse_symbol(self, state, name, is_ignored=False, is_token=False):
        key = (state.offset, name, is_ignored, is_token)
        if key in self._table:
            yield State(offset, blocked=key)
            return

        self._table[key] = []
        for st in self._parse_symbol0(state, name, is_ignored, is_token):
            self._table[key].append(st)
            yield st

        for cont in self._blocked[key]:
            for st in self._table[key]:
                yield from cont(st)

        del self._table[key]
        del self._blocked[key]

    def _parse_symbol0(self, state, name, is_ignored=False, is_token=False):
        expr = self.parser.grammar.get_rule(name)

        if is_ignored or name[0] == "_":
            yield from self._parse_expr(state, expr, is_ignored=True)
            return

        results = state.results
        is_token = is_token or name[0].isupper()
        for st in self._parse_expr(evolve(state, results=[]), expr, is_token=is_token):
            def cont(st):
                args = st.results
                if is_token:
                    result = "".join(args)
                    if visit_token := self.parser._method_map.get(name):
                        result = visit_token(result)
                elif method := self.parser._method_map.get(name):
                    result = method(*args)
                else:
                    result = self.parser.visitor.visit(name, *args)

                yield evolve(st, results=results + [result])
            yield from cont(st)

    def _parse_expr(self, state, expr, **kwargs):
        match expr:
            case Alt(exprs):
                yield from self._parse_alt(state, exprs, **kwargs)
            case Cat(exprs):
                yield from self._parse_cat(state, exprs, **kwargs)
            case String(value):
                yield from self._parse_string(state, value, **kwargs)
            case Symbol(name):
                yield from self._parse_symbol(state, name, **kwargs)
            case Repeat(expr, min, max):
                yield from self._parse_repeat(state, expr, min, max, **kwargs)
            case Charset(groups):
                yield from self._parse_charset(state, groups, **kwargs)
            case CharsetDiff(base, diff):
                yield from self._parse_charset_diff(state, base, diff, **kwargs)
            case _:
                raise NotImplementedError(f"Unknown expr type: {type(expr).__name__}")

    def _parse_alt(self, state, exprs, **kwargs):
        for e in exprs:
            yield from self._parse_expr(state, e, **kwargs)

    def _parse_cat(self, state, exprs, **kwargs):
        if not exprs:
            yield state
            return
        expr, *exprs = exprs
        for st in self._parse_expr(state, expr, **kwargs):
            def cont(st):
                yield from self._parse_cat(st, exprs, **kwargs)
            yield from cont(st)

    def _parse_repeat(self, state, expr, min, max, **kwargs):
        def dec(x):
            if x is None:
                return None
            if x == 0:
                return 0
            return x - 1

        if max is None or max > 0:
            for st in self._parse_expr(state, expr, **kwargs):
                def cont(st):
                    yield from self._parse_repeat(st, expr, dec(min), dec(max), **kwargs)
                yield from cont(st)
        if min == 0:
            yield state

    def _parse_string(self, state, value, is_ignored=False, **kwargs):
        start = state.offset
        end = start + len(value)
        if self.text[start:end] != value:
            return

        results = state.results
        if not is_ignored:
            results = results + [value]
        yield evolve(state, offset=end, results=results)

    def _parse_charset(self, state, groups, is_ignored=False, **kwargs):
        if state.offset >= len(self.text):
            return
        ch = self.text[state.offset]
        has_match = False
        for g in groups:
            match g:
                case Char(c):
                    if ch == c:
                        has_match = True
                        break
                case CharRange(start, end):
                    if start.char <= ch <= end.char:
                        has_match = True
                        break
                case _:
                    raise NotImplementedError(
                        f"Unknown charset group: {type(g).__name__}"
                    )
        if not has_match:
            return

        offset = state.offset + 1
        results = state.results
        if not is_ignored:
            results = results + [ch]
        yield evolve(state, offset=offset, results=results)

    def _parse_charset_diff(self, state, base, diff, **kwargs):
        for st in self._parse_expr(state, base, **kwargs):
            def cont(st):
                # Char matches base, so exclude if matches diff.
                try:
                    next(self._parse_expr(state, diff, **kwargs))
                except StopIteration:
                    yield st
            yield from cont(st)


if __name__ == "__main__":
    g = Grammar.create(
        s=Alt.create(Cat.create(Symbol("A"), Symbol("s")), Symbol("B")),
        A=String("a"),
        B=String("b"),
    )
    print(g)
    print(Parser(g).first_full_parse("aaab"))
    print()

    g = Grammar.create(
        s=Alt.create(
            Cat.create(Symbol("A1"), Symbol("s")),
            Cat.create(Symbol("A2"), Symbol("s")),
            Symbol("A"),
        ),
        A=String("a"),
        A1=String("a"),
        A2=String("a"),
    )
    print(g)
    for result in Parser(g).full_parse("aaaa"):
        print(result)
    print()

    g = Grammar.create(
        s=Repeat(String("a"), min=2),
    )
    print(g)
    print(Parser(g).first_full_parse("aa"))
    print(Parser(g).first_full_parse("aaa"))
    print(Parser(g).first_full_parse("aaaa"))
    print()
