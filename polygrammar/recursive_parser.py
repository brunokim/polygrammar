import inspect
from textwrap import dedent
from typing import Any

from attrs import define, evolve, field, frozen
from attrs.validators import instance_of

from polygrammar.model import *
from polygrammar.model import symbols

__all__ = ["Parser", "ParseError"]


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

    _rule_map: dict = field(init=False, factory=dict)
    _method_map: dict = field(init=False, factory=dict)

    def __attrs_post_init__(self):
        seen = set()
        for rule in self.grammar.rules:
            name = rule.name.name
            method_name = f"visit_{name}"
            if hasattr(self.visitor, method_name):
                self._method_map[name] = getattr(self.visitor, method_name)

            if name in self._rule_map:
                raise ValueError(f"Duplicate rule name: {name}")

            seen |= symbols(rule.expr)

            self._rule_map[name] = rule.expr

        if missing := seen - self._rule_map.keys():
            raise ValueError(f"Undefined rule(s): {', '.join(missing)}")

    def parse(self, text, start=None, offset=0, debug=True):
        if start is None:
            start = self.grammar.rules[0].name.name
        job = ParseJob(self, text)
        yield from job.parse(start, offset)

        if job._num_solutions > 0:
            return

        if not debug:
            raise ParseError(text, offset, "no match")

        # Redo parsing with a debug offset to get better error info.
        job._debug_offset = job._max_offset
        list(job.parse(start, offset))
        excs = []
        for msg, stack in job._debug_stacks:
            context = " > ".join(f"{name}@{off}" for name, off in stack)
            excs.append(ParseError(text, job._debug_offset, f"{msg} ({context})"))
        raise ExceptionGroup("no match", excs)

    def full_parse(self, text, start=None, debug=True):
        has_full_match = False
        max_error_offset = -1
        for result, offset in self.parse(text, start, debug=debug):
            if offset == len(text):
                has_full_match = True
                yield result
            elif offset > max_error_offset:
                max_error_offset = offset

        if not has_full_match:
            raise ParseError(text, max_error_offset, "trailing characters")

    def first_parse(self, text, start=None, offset=0, debug=True):
        return next(self.parse(text, start, offset, debug))

    def first_full_parse(self, text, start=None, debug=True):
        return next(self.full_parse(text, start, debug))


@define
class State:
    offset: int = field(validator=instance_of(int), default=0)
    results: list[Any] = field(factory=list)


@define
class ParseJob:
    parser: Parser = field(validator=instance_of(Parser))
    text: str = field(validator=instance_of(str))

    _num_solutions: int = field(init=False, default=0)
    _max_offset: int = field(init=False, default=0)
    _debug_offset: int = field(init=False, default=-1)
    _debug_stacks: list = field(init=False, factory=list)

    def parse(self, start, offset):
        self._num_solutions = 0
        self._max_offset = 0
        initial_state = State(offset=offset)
        for state in self._parse_symbol(initial_state, start):
            self._num_solutions += 1
            yield state.results, state.offset

    def _debug(self, msg):
        frame_infos = inspect.stack(context=1)
        stack = []
        for info in frame_infos:
            if self != info.frame.f_locals.get("self"):
                break
            if not info.function.startswith("_parse_"):
                continue
            name = info.function.removeprefix("_parse_")
            if name == "expr":
                continue
            offset = info.frame.f_locals.get("state").offset
            stack.append((name, offset))
        stack.reverse()
        self._debug_stacks.append((msg, stack))

    def _parse_symbol(self, state, name, is_ignored=False, is_token=False):
        expr = self.parser._rule_map[name]

        if is_ignored or name[0] == "_":
            yield from self._parse_expr(state, expr, is_ignored=True)
            return

        results = state.results
        is_token = is_token or name[0].isupper()
        for st in self._parse_expr(evolve(state, results=[]), expr, is_token=is_token):
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

    def _parse_expr(self, state, expr, **kwargs):
        self._max_offset = max(self._max_offset, state.offset)
        match expr:
            case Alt(exprs):
                yield from self._parse_alt(state, exprs, **kwargs)
            case Cat(exprs):
                yield from self._parse_cat(state, exprs, **kwargs)
            case String(value):
                yield from self._parse_string(state, value, **kwargs)
            case Symbol(name):
                yield from self._parse_symbol(state, name, **kwargs)
            case Repeat(expr, min_, max_):
                yield from self._parse_repeat(state, expr, min_, max_, **kwargs)
            case Charset(groups):
                yield from self._parse_charset(state, groups, **kwargs)
            case Diff(base, diff):
                yield from self._parse_diff(state, base, diff, **kwargs)
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
            yield from self._parse_cat(st, exprs, **kwargs)

    def _parse_repeat(self, state, expr, min, max, **kwargs):
        def dec(x):
            if x is None:
                return None
            if x == 0:
                return 0
            return x - 1

        if max is None or max > 0:
            for st in self._parse_expr(state, expr, **kwargs):
                yield from self._parse_repeat(st, expr, dec(min), dec(max), **kwargs)
        if min == 0:
            yield state

    def _parse_string(self, state, value, is_ignored=False, **kwargs):
        start = state.offset
        end = start + len(value)
        if self.text[start:end] != value:
            if state.offset == self._debug_offset:
                self._debug(f"string: {self.text[start:end]!r} != {value!r}")
            return

        results = state.results
        if not is_ignored:
            results = results + [value]
        yield evolve(state, offset=end, results=results)

    def _parse_charset(self, state, groups, is_ignored=False, **kwargs):
        if state.offset >= len(self.text):
            if state.offset == self._debug_offset:
                self._debug("charset: EOF")
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
            if state.offset == self._debug_offset:
                self._debug(f"charset: {ch!r} not in {groups}")
            return

        offset = state.offset + 1
        results = state.results
        if not is_ignored:
            results = results + [ch]
        yield evolve(state, offset=offset, results=results)

    def _parse_diff(self, state, base, diff, **kwargs):
        for st in self._parse_expr(state, base, **kwargs):
            # Text matches base, so exclude if matches diff.
            try:
                next(self._parse_expr(state, diff, **kwargs))
                if state.offset == self._debug_offset:
                    self._debug(f"charset_diff: diff {diff} matched")
            except StopIteration:
                yield st


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
