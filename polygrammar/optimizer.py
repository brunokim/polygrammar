from polygrammar.grammars.python_re_writer import to_python_re
from polygrammar.model import *
from polygrammar.model import is_case_sensitive, is_ignored, is_token
from polygrammar.runtime_model import *


def to_range(group):
    match group:
        case Char(c):
            return (ord(c), ord(c) + 1)
        case CharRange(start, end):
            return (ord(start.char), ord(end.char) + 1)
        case _:
            raise ValueError(f"Invalid group: {group}")


def add_groups(g1, g2):
    # TODO: coalesce redundant groups.
    return g1 + g2


def subtract_groups(base, diff):
    base_ranges = sorted(to_range(g) for g in base)
    diff_ranges = sorted(to_range(g) for g in diff)

    i, j = 0, 0
    while i < len(base_ranges) and j < len(diff_ranges):
        a1, z1 = base_ranges[i]
        a2, z2 = diff_ranges[j]

        if z1 <= a2:
            # ████████      ░░░░░░░░
            # a1      z1    a2      z2
            # No overlap, keep base range.
            i += 1
        elif z2 <= a1:
            # ░░░░░░░░      ████████
            # a2      z2    a1      z1
            # No overlap, skip diff range.
            j += 1
        elif a1 < a2 and z1 <= z2:
            # ████████
            #      ░░░░░░░░
            # a1   a2 z1   z2
            # Overlap, keep left part of base range.
            base_ranges[i] = (a1, a2)
            i += 1
        elif a2 <= a1 and z2 < z1:
            #      ████████
            # ░░░░░░░░
            # a2   a1 z2   z1
            # Overlap, keep right part of base range.
            base_ranges[i] = (z2, z1)
            j += 1
        elif a1 < a2 and z2 < z1:
            # █████████████
            #      ░░░
            # a1   a2 z2   z1
            # Overlap, splitting base range in two.
            base_ranges[i : i + 1] = [(a1, a2), (z2, z1)]
            i += 1
        else:
            #      ███
            # ░░░░░░░░░░░░░
            # a2   a1 z1   z2
            # Overlap, remove base range.
            base_ranges[i : i + 1] = []

    results = []
    for a, z in base_ranges:
        if a + 1 == z:
            results.append(Char(chr(a)))
        else:
            results.append(CharRange(Char(chr(a)), Char(chr(z - 1))))
    return results


def inline_rules(rule_map, method_map):
    seen = set()
    new_rules = {}

    def inline(expr):
        if not isinstance(expr, Symbol):
            return expr

        name = expr.name
        if name in new_rules:
            # Name has already been processed.
            return new_rules[name]
        if name in seen:
            # Name is still being processed, thus this is a self-reference
            # that can't be expanded.
            # Return just the symbol.
            return expr
        seen.add(name)
        base_expr = rule_map[name]
        if name not in method_map or is_token(base_expr) or is_ignored(base_expr):
            # Can't inline elements of rule that has a visitor method,
            # because this may change the number of elements passed to it.
            #
            # The exceptions are tokens and ignored expressions.
            # Tokens can always be inlined, because they pass a single element
            # to the visitor method.
            # Likewise, ignored rules can't have visitors, so no visitor method
            # would be called.
            expr = tree_transform(base_expr, inline)

            # Copy metadata
            expr = expr.update_meta(base_expr.metadata)
            new_rules[name] = expr
        else:
            new_rules[name] = base_expr
        return new_rules[name]

    for name in rule_map:
        inline(Symbol(name))

    return new_rules


@preserve_metadata
def string_to_charset(expr):
    if not isinstance(expr, String):
        return expr
    value = expr.value
    if len(value) != 1:
        return expr
    if is_case_sensitive(expr):
        return Charset.create(value)
    if value.lower() != value.upper():
        return Charset.create(value.lower(), value.upper())
    return Charset.create(value)


@preserve_metadata
def coalesce_charsets(expr):
    match expr:
        case Alt(exprs):
            new_exprs = [exprs[0]]
            for e in exprs[1:]:
                curr = new_exprs[-1]
                if not (isinstance(curr, Charset) and isinstance(e, Charset)):
                    new_exprs.append(e)
                    continue

                if is_token(curr) != is_token(e) or is_ignored(curr) != is_ignored(e):
                    # Don't merge charsets with different token/ignored status.
                    new_exprs.append(e)
                    continue

                # Replace curr charset with charset union.
                new_exprs[-1] = Charset.create(*add_groups(curr.groups, e.groups))
            return Alt.create(*new_exprs)
        case Diff(base, diff):
            match base, diff:
                case Charset(g1), Charset(g2):
                    return Charset.create(*subtract_groups(g1, g2))
                case _:
                    return Diff(base, diff)
        case _:
            return expr


@preserve_metadata
def convert_to_regexp(expr):
    if has_inner_node(expr, lambda x: isinstance(x, (Symbol, Diff)) or is_ignored(x)):
        # Not a regular expression.
        return expr
    if not (is_token(expr) or is_ignored(expr)):
        # Regexp may change number of output tokens.
        return expr
    return Regexp(to_python_re(expr))


@preserve_metadata
def remove_empty(expr):
    match expr:
        case (
            Optional(Empty())
            | ZeroOrMore(Empty())
            | OneOrMore(Empty())
            | Repeat(Empty())
            | Diff(Empty(), _)
        ):
            return Empty()
        case Alt(exprs):
            if not any(isinstance(e, Empty) for e in exprs):
                return expr
            new_exprs = [e for e in exprs if not isinstance(e, Empty)]
            return Optional(Alt.create(*new_exprs))
        case Cat(exprs):
            if not any(isinstance(e, Empty) for e in exprs):
                return expr
            new_exprs = [e for e in exprs if not isinstance(e, Empty)]
            return Cat.create(*new_exprs)
        case Diff(base, Empty()):
            return base
        case _:
            return expr


optimize = compose_rulemap_transforms(
    inline_rules,
    expr_to_rulemap_transform(
        compose_node_transforms(
            string_to_charset,
            coalesce_charsets,
            remove_empty,
        )
    ),
    expr_to_rulemap_transform(convert_to_regexp, order="root"),
)
