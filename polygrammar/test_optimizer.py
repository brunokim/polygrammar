from textwrap import dedent

import pytest

from polygrammar.grammars.ebnf import EBNF_GRAMMAR, parse_ebnf, to_ebnf
from polygrammar.model import *
from polygrammar.optimizer import optimize


@pytest.mark.parametrize(
    "rule_map, want",
    [
        ('s = "a";', "s = [a];"),
        ("s = s;", "s = s;"),
        ('a = b; b = "B";', "a = [B]; b = [B];"),
        ('a = "A" | "B";', "a = [AB];"),
        ('a = [a-z] - "m";', "a = [a-ln-z];"),
        ("a = [a-z] - [p-t];", "a = [a-ou-z];"),
        (
            "a = ([a-c] | [f-n] | 'o' | [p-v] | [u-y]) - [d-e] - [h-k] - [m-q];",
            "a = [a-cf-glr-vu-y];",
        ),
        (
            dedent(
                """\
                s = a | b | c | d;
                a = "A";
                b = "B";
                c = s "C";
                d = "D";
                """
            ),
            dedent(
                """\
                s = [AB] | s [C] | [D];
                a = [A];
                b = [B];
                c = s [C];
                d = [D];
                """
            ),
        ),
    ],
)
def test_optimizer(rule_map, want):
    rule_map = make_rule_map(parse_ebnf(rule_map))
    want = make_rule_map(parse_ebnf(want))
    assert optimize(rule_map) == want


def test_optimize_ebnf():
    rule_map = make_rule_map(EBNF_GRAMMAR)
    optimized = optimize(
        rule_map,
        {
            "grammar",
            "rule",
            "expr",
            "alt",
            "cat",
            "term",
            "repeat",
            "min_max",
            "diff",
            "atom",
        },
    )
    print(to_ebnf(Grammar.create(**optimized)))


def make_rule_map(grammar):
    return {rule.name.name: rule.expr for rule in grammar.rules}
