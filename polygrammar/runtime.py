import inspect
import warnings
from typing import Callable

from attrs import field, frozen
from attrs.validators import deep_mapping, instance_of, is_callable

from polygrammar.model import Alt, Cat, Expr, Grammar, Visitor, symbols
from polygrammar.optimizer import optimize

BASE_OPTIONS = {"ignore", "warn", "error"}


def handle_problem(msg: str, option: str):
    if option == "warn":
        warnings.warn(msg)
    elif option == "error":
        raise ValueError(msg)
    else:
        assert option == "ignore"


DUPLICATE_OPTIONS = {"overrides", "overloads"} | BASE_OPTIONS


def build_rule_map(grammar, on_duplicate_rule="error"):
    if on_duplicate_rule not in DUPLICATE_OPTIONS:
        raise ValueError(
            "on_duplicate_rule must be one of {', '.join(DUPLICATE_OPTIONS)}"
        )

    # Map rule names to expressions.
    rule_map = {}
    duplicate_rules = []
    for rule in grammar.rules:
        name = rule.name.name
        expr = rule.expr
        if name not in rule_map or on_duplicate_rule == "overrides":
            rule_map[name] = expr
            continue
        if rule.is_additional_alt or on_duplicate_rule == "overloads":
            rule_map[name] = Alt.create(rule_map[name], expr)
            continue
        if rule.is_additional_cat:
            rule_map[name] = Cat.create(rule_map[name], expr)
            continue
        duplicate_rules.append(name)

    if duplicate_rules:
        handle_problem(
            f"Duplicate rule(s): {', '.join(duplicate_rules)}", on_duplicate_rule
        )

    # Report missing rules.
    seen = set()
    for expr in rule_map.values():
        seen |= symbols(expr)
    if missing := seen - rule_map.keys():
        raise ValueError(f"Undefined rule(s): {', '.join(missing)}")

    return rule_map


def build_method_map(rule_names, visitor, on_unused_visitor_methods="error"):
    if on_unused_visitor_methods not in BASE_OPTIONS:
        raise ValueError(
            "on_unused_visitor_methods must be one of {', '.join(BASE_OPTIONS)}"
        )
    method_map = {}

    # Map visitor methods.
    methods = inspect.getmembers(visitor, predicate=inspect.ismethod)
    method_names = {
        method_name: f for method_name, f in methods if method_name.startswith("visit_")
    }
    for name in rule_names:
        method_name = "visit_" + name.replace("-", "_")
        if f := method_names.pop(method_name, None):
            method_map[name] = f

    # Report unused visitor methods.
    if method_names:
        handle_problem(
            f"Unused visitor method(s): {', '.join(method_names)}",
            on_unused_visitor_methods,
        )

    return method_map


@frozen
class Runtime:
    rule_map: dict[str, Expr] = field(
        validator=deep_mapping(instance_of(str), instance_of(Expr))
    )
    method_map: dict[str, Callable] = field(
        validator=deep_mapping(instance_of(str), is_callable())
    )

    @classmethod
    def from_grammar(
        cls,
        grammar: Grammar,
        visitor: Visitor = None,
        on_duplicate_rule: str = "error",
        on_unused_visitor_methods: str = "error",
        rule_transforms=None,
        rule_map_transforms=None,
    ):
        if visitor is None:
            visitor = Visitor()
        if rule_transforms is None:
            rule_transforms = [
                ignored_rule_starts_with_underscore,
                token_rule_starts_with_uppercase,
            ]
        if rule_map_transforms is None:
            rule_map_transforms = [optimize]

        rule_map = build_rule_map(grammar, on_duplicate_rule)
        method_map = build_method_map(
            rule_map.keys(), visitor, on_unused_visitor_methods
        )

        for f in rule_transforms:
            rule_map = {name: f(name, expr) for name, expr in rule_map.items()}
        for f in rule_map_transforms:
            rule_map = f(rule_map, method_map.keys())

        return cls(rule_map=rule_map, method_map=method_map)


def ignored_rule_starts_with_underscore(name, expr):
    if name[0] == "_":
        return expr.with_meta("ignore")
    return expr


def token_rule_starts_with_uppercase(name, expr):
    if name[0].isupper():
        return expr.with_meta("token")
    return expr
