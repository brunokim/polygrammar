from polygrammar.model import *


def to_range(group):
    match group:
        case Char(c):
            return (ord(c), ord(c) + 1)
        case CharRange(start, end):
            return (ord(start.char), ord(end.char) + 1)
        case _:
            raise ValueError(f"Invalid group: {group}")


def subtract_groups(base, diff):
    base_ranges = sorted(to_range(g) for g in base)
    diff_ranges = sorted(to_range(g) for g in diff)

    i, j = 0, 0
    while i < len(base_ranges) and j < len(diff_ranges):
        a1, z1 = base_ranges[i]
        a2, z2 = diff_ranges[j]

        if z1 <= a2:
            # [a1,  z1)
            #           [a2,  z2)
            # No overlap, keep base range.
            i += 1
        elif z2 <= a1:
            #           [a1,  z1)
            # [a2,  z2)
            # No overlap, skip diff range.
            j += 1
        elif a1 < a2 and z1 <= z2:
            # [a1,       z1)
            #      [a2,       z2)
            # Overlap, keep left part of base range.
            base_ranges[i] = (a1, a2)
            i += 1
        elif a2 <= a1 and z2 < z1:
            #      [a1,       z1)
            # [a2,       z2)
            # Overlap, keep right part of base range.
            base_ranges[i] = (z2, z1)
            j += 1
        elif a1 < a2 and z2 < z1:
            # [a1,            z1)
            #      [a2,  z2)
            # Overlap, splitting base range in two.
            base_ranges[i : i + 1] = [(a1, a2), (z2, z1)]
            i += 1
        else:
            #      [a1,  z1)
            # [a2,            z2)
            # Overlap, remove base range.
            base_ranges[i : i + 1] = []

    results = []
    for a, z in base_ranges:
        if a + 1 == z:
            results.append(Char(chr(a)))
        else:
            results.append(CharRange(Char(chr(a)), Char(chr(z - 1))))
    return results


def optimize(rule_map, with_visitor=None):
    if with_visitor is None:
        with_visitor = set()
    seen = set()
    visited = set()

    def optimize_expr(expr):
        match expr:
            case String(value):
                if len(value) == 1:
                    return Charset.create(value)
                return expr
            case Symbol(name):
                if name in with_visitor:
                    # Do not inline names that must be called by visitor.
                    return rule_map[name]
                if name in seen and name not in visited:
                    # Self-referential name can't be inlined.
                    return expr
                seen.add(name)
                if name not in visited:
                    rule_map[name] = optimize_expr(rule_map[name])
                visited.add(name)
                return rule_map[name]
            case Alt(exprs):
                new_exprs = []
                for e in exprs:
                    e = optimize_expr(e)
                    if not new_exprs:
                        new_exprs.append(e)
                        continue
                    curr = new_exprs[-1]
                    match curr, e:
                        case Charset(g1), Charset(g2):
                            new_exprs[-1] = Charset(g1 + g2)
                        case _:
                            new_exprs.append(e)
                return Alt.create(*new_exprs)
            case Diff(base, diff):
                base = optimize_expr(base)
                diff = optimize_expr(diff)
                match base, diff:
                    case Charset(g1), Charset(g2):
                        return Charset(subtract_groups(g1, g2))
                    case _:
                        return Diff(base, diff)
            case Cat(exprs):
                return Cat(optimize_expr(e) for e in exprs)
            case Repeat(expr, min, max):
                return Repeat.create(optimize_expr(expr), min=min, max=max)
            case _:
                return expr

    return {name: optimize_expr(Symbol(name)) for name, expr in rule_map.items()}
