import inspect
from textwrap import dedent
from typing import Any

from attrs import define, evolve, field, frozen
from attrs.validators import instance_of, optional

from polygrammar.model import *
from polygrammar.model import is_case_sensitive, is_ignored, is_token
from polygrammar.runtime import Runtime

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
    grammar: Grammar | None = field(
        validator=optional(instance_of(Grammar)), default=None
    )
    visitor: Visitor | None = field(
        validator=optional(instance_of(Visitor)), default=None
    )
    _rt: Runtime | None = field(validator=optional(instance_of(Runtime)), default=None)

    @classmethod
    def from_grammar(cls, grammar, visitor=None, **kwargs):
        if visitor is None:
            visitor = Visitor()
        rt = Runtime.from_grammar(grammar, visitor, **kwargs)
        return cls(grammar, visitor, rt)

    def parse(self, text, expr=None, offset=0, debug=True):
        if expr is None:
            if self.grammar is None or not self.grammar.rules:
                raise ValueError("No grammar or rules defined")
            expr = self.grammar.rules[0].name
        job = ParseJob(self, text)
        yield from job.parse(expr, offset)

        if job._num_solutions > 0:
            return

        if not debug:
            raise ParseError(text, offset, "no match")

        # Redo parsing with a debug offset to get better error info.
        job._debug_offset = job._max_offset
        list(job.parse(expr, offset))
        excs = []
        for msg, stack in job._debug_stacks:
            context = " > ".join(f"{name}@{off}" for name, off in stack)
            excs.append(ParseError(text, job._debug_offset, f"{msg} ({context})"))
        raise ExceptionGroup("no match", excs)

    def first_parse(self, text, expr=None, offset=0, debug=True):
        return next(self.parse(text, expr, offset, debug))


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

    def parse(self, expr, offset):
        self._num_solutions = 0
        self._max_offset = 0
        initial_state = State(offset=offset)
        for state in self._parse_expr(initial_state, expr):
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

    def _parse_symbol(self, state, name, ignore=False, token=False):
        if self.parser._rt is None:
            raise ValueError("Can't parse symbol {name!r}, no grammar provided")
        expr = self.parser._rt.rule_map[name]

        if ignore or is_ignored(expr):
            yield from self._parse_expr(state, expr, ignore=True)
            return

        results = state.results
        for st in self._parse_expr(evolve(state, results=[]), expr, token=token):
            args = st.results
            if token or is_token(expr):
                result = "".join(args)
                if visit_token := self.parser._rt.method_map.get(name):
                    result = visit_token(result)
            elif method := self.parser._rt.method_map.get(name):
                result = method(*args)
            else:
                result = self.parser.visitor.visit(name, *args)

            yield evolve(st, results=results + [result])

    def _parse_expr(self, state, expr, **kwargs):
        self._max_offset = max(self._max_offset, state.offset)
        if is_ignored(expr):
            kwargs["ignore"] = True
        if is_token(expr):
            kwargs["token"] = True
        match expr:
            case Alt(exprs):
                yield from self._parse_alt(state, exprs, **kwargs)
            case Cat(exprs):
                yield from self._parse_cat(state, exprs, **kwargs)
            case String(value):
                yield from self._parse_string(
                    state, value, is_case_sensitive(expr), **kwargs
                )
            case Symbol(name):
                yield from self._parse_symbol(state, name, **kwargs)
            case Repeat(expr, min_, max_):
                yield from self._parse_repeat(state, expr, min_, max_, **kwargs)
            case Optional(expr):
                yield from self._parse_repeat(state, expr, 0, 1, **kwargs)
            case ZeroOrMore(expr):
                yield from self._parse_repeat(state, expr, 0, None, **kwargs)
            case OneOrMore(expr):
                yield from self._parse_repeat(state, expr, 1, None, **kwargs)
            case Charset(groups):
                yield from self._parse_charset(state, groups, **kwargs)
            case Diff(base, diff):
                yield from self._parse_diff(state, base, diff, **kwargs)
            case EndOfFile():
                yield from self._parse_end_of_file(state, **kwargs)
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

    def _parse_string(self, state, value, case_sensitive, ignore=False, **kwargs):
        start = state.offset
        end = start + len(value)

        text = self.text[start:end]
        if case_sensitive:
            is_match = text == value
        else:
            is_match = text.lower() == value.lower()

        if not is_match:
            if state.offset == self._debug_offset:
                self._debug(
                    f"string: {self.text[start:end]!r} != {value!r} ({case_sensitive=})"
                )
            return

        results = state.results
        if not ignore:
            results = results + [text]
        yield evolve(state, offset=end, results=results)

    def _parse_charset(self, state, groups, ignore=False, **kwargs):
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
        if not ignore:
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

    def _parse_end_of_file(self, state, **kwargs):
        if state.offset == len(self.text):
            yield evolve(state, offset=state.offset + 1)
        elif state.offset == self._debug_offset:
            self._debug("EOF: not at end of file")
