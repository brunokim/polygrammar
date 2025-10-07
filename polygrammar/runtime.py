import inspect
import warnings
from typing import Callable

from attrs import field, frozen
from attrs.validators import deep_mapping, instance_of, is_callable

from polygrammar.model import Alt, Cat, Expr, Grammar, Symbol, Visitor, symbols


def handle_problem(msg: str, option: str):
    if option == "warn":
        warnings.warn(msg)
    elif option == "error":
        raise ValueError(msg)
    else:
        assert option == "ignore"


BASE_OPTIONS = {"ignore", "warn", "error"}
DUPLICATE_OPTIONS = {"overrides", "overloads"} | BASE_OPTIONS


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
    ):
        if visitor is None:
            visitor = Visitor()
        if on_duplicate_rule not in DUPLICATE_OPTIONS:
            raise ValueError(
                "on_duplicate_rule must be one of {', '.join(DUPLICATE_OPTIONS)}"
            )
        if on_unused_visitor_methods not in BASE_OPTIONS:
            raise ValueError(
                "on_unused_visitor_methods must be one of {', '.join(BASE_OPTIONS)}"
            )
        rule_map = {}
        method_map = {}

        # Map rule names to expressions.
        duplicate_rules = []
        for rule in grammar.rules:
            name = rule.name.name
            if name[0] == "_":
                rule.expr.__meta__.append(Symbol("ignore"))
            if name[0].isupper():
                rule.expr.__meta__.append(Symbol("token"))
            if name not in rule_map or on_duplicate_rule == "overrides":
                rule_map[name] = rule.expr
                continue
            if rule.is_additional_alt or on_duplicate_rule == "overloads":
                rule_map[name] = Alt.create(rule_map[name], rule.expr)
                continue
            if rule.is_additional_cat:
                rule_map[name] = Cat.create(rule_map[name], rule.expr)
                continue
            duplicate_rules.append(name)

        if duplicate_rules:
            handle_problem(
                f"Duplicate rule(s): {', '.join(duplicate_rules)}", on_duplicate_rule
            )

        # Find missing rules.
        seen = set()
        for expr in rule_map.values():
            seen |= symbols(expr)
        if missing := seen - rule_map.keys():
            raise ValueError(f"Undefined rule(s): {', '.join(missing)}")

        # Map visitor methods.
        methods = inspect.getmembers(visitor, predicate=inspect.ismethod)
        method_names = {
            method_name: f
            for method_name, f in methods
            if method_name.startswith("visit_")
        }
        for name in rule_map.keys():
            method_name = "visit_" + name.replace("-", "_")
            if f := method_names.pop(method_name, None):
                method_map[name] = f

        # Find unused visitor methods.
        if method_names:
            handle_problem(
                f"Unused visitor method(s): {', '.join(method_names)}",
                on_unused_visitor_methods,
            )

        return cls(rule_map=rule_map, method_map=method_map)
