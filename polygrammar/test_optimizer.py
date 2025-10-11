from textwrap import dedent

import pytest

from polygrammar.grammars.ebnf import EBNF_GRAMMAR, parse_ebnf, to_ebnf
from polygrammar.model import *
from polygrammar.optimizer import inline_rules, optimize
from polygrammar.runtime import build_rule_map


@pytest.mark.parametrize(
    "grammar, has_visitor, output",
    [
        ('A = "a"; AA = A A;', {}, 'A = "a"; AA = "a" "a";'),
        ('AA = A A; A = "a";', {}, 'AA = "a" "a"; A = "a";'),
        ('A = "a"; AA = A A;', {"A"}, 'A = "a"; AA = "a" "a";'),
        ('A = "a"; aa = A A;', {"aa"}, 'A = "a"; aa = A A;'),
        ('A = "a"; AA = A A;', {"AA"}, 'A = "a"; AA = "a" "a";'),
        ('s = "s"; a = s | s;', {}, 's = "s"; a = "s" | "s";'),
        ('s = "s"; a = s?;', {}, 's = "s"; a = "s"?;'),
        ('s = "s"; a = s*;', {}, 's = "s"; a = "s"*;'),
        ('s = "s"; a = s+;', {}, 's = "s"; a = "s"+;'),
        ('s = "s"; a = s{1,2};', {}, 's = "s"; a = "s"{1,2};'),
        ('s = "s"; a = s - s;', {}, 's = "s"; a = "s" - "s";'),
        ('s = "s"; a = s | s (s - s)+;', {}, 's = "s"; a = "s" | "s" ("s" - "s")+;'),
        ('s = A s | B; A = "a"; B = "b";', {}, 's = "a" s | "b"; A = "a"; B = "b";'),
    ],
)
def test_inline_rules(grammar, has_visitor, output):
    rule_map = build_rule_map(parse_ebnf(grammar))
    want = build_rule_map(parse_ebnf(output))
    assert inline_rules(rule_map, has_visitor) == want


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
    rule_map = build_rule_map(parse_ebnf(rule_map))
    want = build_rule_map(parse_ebnf(want))
    assert optimize(rule_map) == want


def test_inline_rules_ebnf():
    rule_map = build_rule_map(EBNF_GRAMMAR)
    optimized = inline_rules(
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
