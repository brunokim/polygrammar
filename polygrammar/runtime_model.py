from functools import wraps
from typing import Callable

from polygrammar.model import *
from polygrammar.model import transform

__all__ = [
    "RuleMap",
    "MethodMap",
    "preserve_metadata",
    "compose_node_transforms",
    "compose_rule_transforms",
    "compose_rulemap_transforms",
    "node_to_rule_transform",
    "rule_expr_to_rule_transform",
    "rule_to_rulemap_transform",
    "node_to_rulemap_transform",
    "rule_expr_to_rulemap_transform",
]


RuleMap = dict[str, Expr]
MethodMap = dict[str, Callable]


def preserve_metadata(f):
    @wraps(f)
    def wrapper(node):
        return f(node).update_meta(node.metadata)

    return wrapper


def compose_node_transforms(*fs):
    def node_transform(node):
        for f in fs:
            node = f(node)
        return node

    return node_transform


def compose_rule_transforms(*fs):
    def rule_transform(name, expr):
        for f in fs:
            expr = f(name, expr)
        return expr

    return rule_transform


def compose_rulemap_transforms(*fs):
    def rulemap_transform(rule_map, method_map):
        for f in fs:
            rule_map = f(rule_map, method_map)
        return rule_map

    return rulemap_transform


def node_to_rule_transform(f):
    def rule_transform(name, expr):
        return transform(expr, f)

    return rule_transform


def rule_expr_to_rule_transform(f):
    def rule_transform(name, expr):
        return f(expr)

    return rule_transform


def rule_to_rulemap_transform(f):
    def rulemap_transform(rule_map, method_map):
        return {name: f(name, expr) for name, expr in rule_map.items()}

    return rulemap_transform


def node_to_rulemap_transform(f):
    rule_transform = node_to_rule_transform(f)
    rulemap_transform = rule_to_rulemap_transform(rule_transform)
    return rulemap_transform


def rule_expr_to_rulemap_transform(f):
    rule_transform = rule_expr_to_rule_transform(f)
    rulemap_transform = rule_to_rulemap_transform(rule_transform)
    return rulemap_transform
