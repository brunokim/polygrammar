from textwrap import dedent

import pytest

from polygrammar.grammars.ebnf import EBNF_GRAMMAR, parse_ebnf, to_ebnf
from polygrammar.model import *
from polygrammar.optimizer import (
    coalesce_charsets,
    inline_rules,
    optimize,
    string_to_charset,
)
from polygrammar.runtime import build_rule_map
from polygrammar.transforms import expr_to_rulemap_transform


@pytest.mark.parametrize(
    "grammar, has_visitor, output",
    [
        ('A = "a"; AA = A A;', {}, 'A = "a"; AA = "a" "a";'),
        ('AA = A A; A = "a";', {}, 'AA = "a" "a"; A = "a";'),
        ('A = "a"; AA = A A;', {"A"}, 'A = "a"; AA = "a" "a";'),
        ('A = "a"; aa = A A;', {"aa"}, 'A = "a"; aa = A A;'),
        pytest.param(
            'A = "a"; AA = A A;',
            {"AA"},
            'A = "a"; AA = "a" "a";',
            marks=[pytest.mark.skip],
        ),
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
    "expr, want",
    [
        (String("A"), Charset.create(Char("A"))),
        (String("b").set_meta("i"), Charset.create(Char("b"), Char("B"))),
        (String("C").set_meta("s"), Charset.create(Char("C"))),
        (String("/").set_meta("i"), Charset.create(Char("/"))),
        (String("efg"), String("efg")),
    ],
)
def test_string_to_charset(expr, want):
    assert string_to_charset(expr) == want


@pytest.mark.parametrize(
    "grammar, want",
    [
        ("s = [abc] | [def];", "s = [abcdef];"),
        ("s = [abc] - [def];", "s = [abc];"),
        ("s = [a-f] - [def];", "s = [a-c];"),
        ("s = [a-z] - [def];", "s = [a-cg-z];"),
        ("s = [d-f] - [a-z];", "s = '';"),
        ("s = [b-gj-rt-wy-z] - [a-cf-hl-x];", "s = [d-ej-ky-z];"),
        ("s = [abc] | [def] | 'str' ;", "s = [abcdef] | 'str' ;"),
        ("s = [abc] | 'str' | [def] ;", "s = [abc] | 'str' | [def] ;"),
        ("s = [a-z] - [m];", "s = [a-ln-z];"),
        ("s = [a-f] - [u-z];", "s = [a-f];"),
        ("s = [u-z] - [a-f];", "s = [u-z];"),
        ("s = [a-f] - [d-z];", "s = [a-c];"),
        ("s = [f-z] - [a-m];", "s = [n-z];"),
        ("s = [a-z] - [f-m];", "s = [a-en-z];"),
        ("s = [f-m] - [a-z];", "s = '';"),
    ],
)
def test_coalesce_charsets(grammar, want):
    rule_map = build_rule_map(parse_ebnf(grammar))
    want = build_rule_map(parse_ebnf(want))
    rulemap_transform = expr_to_rulemap_transform(coalesce_charsets)
    assert rulemap_transform(rule_map, {}) == want


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
    assert optimize(rule_map, {}) == want


def test_optimize_ebnf():
    rule_map = optimize(
        build_rule_map(EBNF_GRAMMAR),
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
    print(to_ebnf(Grammar.create(**rule_map)))
