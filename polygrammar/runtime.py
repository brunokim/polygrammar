import inspect
import warnings
from typing import ClassVar, Sequence

from attrs import field, frozen
from attrs.validators import deep_mapping, instance_of, is_callable
from frozendict import frozendict

from polygrammar.model import (
    Alt,
    Cat,
    Directive,
    Expr,
    Grammar,
    MethodMap,
    Rule,
    RuleMap,
    Symbol,
    Visitor,
)
from polygrammar.optimizer import optimize
from polygrammar.transforms import (
    compose_rulemap_transforms,
    rule_to_rulemap_transform,
    symbols,
)

BASE_OPTIONS = {"ignore", "warn", "error"}


def handle_problem(msg: str, option: str):
    if option == "warn":
        warnings.warn(msg)
    elif option == "error":
        raise ValueError(msg)
    else:
        assert option == "ignore", f"option {option!r} not supported"


DUPLICATE_OPTIONS = {"overrides", "overloads"} | BASE_OPTIONS


@frozen
class Runtime:
    rule_map: RuleMap = field(
        converter=frozendict,
        validator=deep_mapping(instance_of(str), instance_of(Expr)),
    )
    method_map: MethodMap = field(
        converter=frozendict, validator=deep_mapping(instance_of(str), is_callable())
    )

    _runtime_cache: ClassVar[dict[Grammar, "Runtime"]] = {}

    @classmethod
    def from_grammar(
        cls,
        grammar: Grammar,
        visitor: Visitor = None,
        on_duplicate_rule: str = "error",
        on_unused_visitor_methods: str = "error",
        rulemap_transforms=None,
        catalog=None,
        use_cache=False,
    ):
        if use_cache and grammar in cls._runtime_cache:
            return cls._runtime_cache[grammar]
        if visitor is None:
            visitor = Visitor()
        if rulemap_transforms is None:
            rulemap_transforms = [
                rule_to_rulemap_transform(ignored_rule_starts_with_underscore),
                rule_to_rulemap_transform(token_rule_starts_with_uppercase),
                optimize,
            ]

        rule_map = cls.build_rule_map(grammar, on_duplicate_rule, catalog=catalog)
        method_map = cls.build_method_map(
            rule_map.keys(), visitor, on_unused_visitor_methods
        )

        rulemap_transform = compose_rulemap_transforms(*rulemap_transforms)
        rule_map = rulemap_transform(rule_map, method_map)

        rt = cls(rule_map=rule_map, method_map=method_map)
        if use_cache:
            cls._runtime_cache[grammar] = rt
        return rt

    @classmethod
    def _import_rule(cls, catalog, grammar_ref, symbol, alias=None):
        if isinstance(grammar_ref, Symbol):
            grammar_ref = grammar_ref.name
        if isinstance(symbol, Symbol):
            symbol = symbol.name
        if alias is None:
            alias = symbol
        elif isinstance(alias, Symbol):
            alias = alias.name

        other_grammar = catalog[grammar_ref]
        other_rt = cls.from_grammar(other_grammar, use_cache=True)
        rule = Rule(Symbol(alias), other_rt.rule_map[symbol])
        return rule

    @classmethod
    def _run_directive(cls, directive, catalog):
        match directive:
            case Directive(Symbol("import"), [grammar_ref, symbol]):
                return cls._import_rule(catalog, grammar_ref, symbol)
            case Directive(Symbol("import"), [grammar_ref, symbol, alias]):
                return cls._import_rule(catalog, grammar_ref, symbol, alias)
            case Directive(Symbol("ignore"), [symbol]):
                return Rule(Symbol("_ignored_tokens"), symbol, is_additional_alt=True)
            case _:
                raise NotImplementedError(directive)

    @classmethod
    def build_rule_map(
        cls, grammar: Grammar, on_duplicate_rule="error", catalog=None
    ) -> RuleMap:
        if on_duplicate_rule not in DUPLICATE_OPTIONS:
            raise ValueError(
                "on_duplicate_rule must be one of {', '.join(DUPLICATE_OPTIONS)}"
            )

        # Map rule names to expressions.
        rule_map = {}
        duplicate_rules = []
        for rule in grammar.rules:
            if isinstance(rule, Directive):
                rule = cls._run_directive(rule, catalog)

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

    @classmethod
    def build_method_map(
        cls,
        rule_names: Sequence[str],
        visitor: Visitor,
        on_unused_visitor_methods="error",
    ) -> MethodMap:
        if on_unused_visitor_methods not in BASE_OPTIONS:
            raise ValueError(
                "on_unused_visitor_methods must be one of {', '.join(BASE_OPTIONS)}"
            )
        method_map = {}

        # Map visitor methods.
        methods = inspect.getmembers(visitor, predicate=inspect.ismethod)
        method_names = {
            method_name: f
            for method_name, f in methods
            if method_name.startswith("visit_")
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


def ignored_rule_starts_with_underscore(name, expr):
    if name[0] == "_":
        return expr.set_meta("ignore")
    return expr


def token_rule_starts_with_uppercase(name, expr):
    if name[0].isupper():
        return expr.set_meta("token")
    return expr
