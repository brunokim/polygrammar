from functools import wraps
from typing import Callable

from polygrammar.model import *

__all__ = [
    "tree_transform",
    "compose_node_transforms",
    "compose_rule_transforms",
    "compose_rulemap_transforms",
    "expr_to_rule_transform",
    "rule_to_rulemap_transform",
    "expr_to_rulemap_transform",
    "symbols",
    "has_inner_node",
    "preserve_metadata",
]

# Transformation types

NodeTransform = Callable[Node, Node]
RuleTransform = Callable[[str, Expr], Expr]
RulemapTransform = Callable[[RuleMap, MethodMap], RuleMap]


# Recursive primitives


def tree_transform(node: Node, f: NodeTransform, *, order: str = "post") -> Node:
    if order == "root":
        return f(node)
    if order == "post":
        if not node.children:
            return f(node)
        cls = type(node)
        children = (tree_transform(c, f, order=order) for c in node.children)
        x = cls.create(*children, metadata=node.metadata, **node.attributes)
        return f(x)
    raise NotImplementedError(f"tree traversal order not implemented: {order!r}")


def walk(node, f):
    for child in node.children:
        yield from walk(child, f)
    yield from f(node)


# Higher-order function composition


def compose_node_transforms(*fs: NodeTransform) -> NodeTransform:
    def node_transform(node):
        for f in fs:
            node = f(node)
        return node

    return node_transform


def compose_rule_transforms(*fs: RuleTransform) -> RuleTransform:
    def rule_transform(name, expr):
        for f in fs:
            expr = f(name, expr)
        return expr

    return rule_transform


def compose_rulemap_transforms(*fs: RulemapTransform) -> RulemapTransform:
    def rulemap_transform(rule_map, method_map):
        for f in fs:
            rule_map = f(rule_map, method_map)
        return rule_map

    return rulemap_transform


# Higher-order conversion between transformations.


def expr_to_rule_transform(f: NodeTransform, order: str = "post") -> RuleTransform:
    def rule_transform(name, expr):
        return tree_transform(expr, f, order=order)

    return rule_transform


def rule_to_rulemap_transform(f: RuleTransform) -> RulemapTransform:
    def rulemap_transform(rule_map, method_map):
        return {name: f(name, expr) for name, expr in rule_map.items()}

    return rulemap_transform


def expr_to_rulemap_transform(
    f: NodeTransform, order: str = "post"
) -> RulemapTransform:
    rule_transform = expr_to_rule_transform(f, order=order)
    rulemap_transform = rule_to_rulemap_transform(rule_transform)
    return rulemap_transform


# Recursive walk


def symbols(node: Node):
    seen = set()

    def walk(x):
        if isinstance(x, Symbol):
            seen.add(x.name)
            return
        for c in x.children:
            walk(c)

    walk(node)
    return seen


def has_inner_node(node: Node, pred: Callable[Node, bool]):
    found = False

    def walk(x):
        nonlocal found
        found = found or pred(x)
        if found:
            return
        for c in x.children:
            walk(c)

    walk(node)
    return found


# Annotations


def preserve_metadata(f: NodeTransform) -> NodeTransform:
    @wraps(f)
    def wrapper(node):
        return f(node).update_meta(node.metadata)

    return wrapper
