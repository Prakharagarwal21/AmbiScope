from __future__ import annotations

from .constants import ENDMARKER, EPSILON


def first_of_sequence(sequence: list[str], first_sets: dict[str, set[str]]) -> set[str]:
    result: set[str] = set()
    if not sequence:
        result.add(EPSILON)
        return result

    all_nullable = True
    for symbol in sequence:
        first = first_sets.get(symbol, {symbol})
        result |= {t for t in first if t != EPSILON}
        if EPSILON not in first:
            all_nullable = False
            break

    if all_nullable:
        result.add(EPSILON)
    return result


def compute_first_sets(grammar) -> dict[str, set[str]]:
    first_sets: dict[str, set[str]] = {}

    for t in grammar.terminals:
        first_sets[t] = {t}
    for nt in grammar.nonterminals:
        first_sets[nt] = set()
    first_sets[EPSILON] = {EPSILON}
    first_sets[ENDMARKER] = {ENDMARKER}

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            first_a = first_sets[prod.lhs]
            first_alpha = first_of_sequence(list(prod.rhs), first_sets)
            if first_alpha - first_a:
                first_a |= first_alpha
                changed = True

    return first_sets


def compute_follow_sets(grammar, first_sets: dict[str, set[str]]) -> dict[str, set[str]]:
    follow_sets: dict[str, set[str]] = {nt: set() for nt in grammar.nonterminals}
    follow_sets[grammar.start_symbol].add(ENDMARKER)

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            rhs = list(prod.rhs)
            for idx, symbol in enumerate(rhs):
                if symbol not in grammar.nonterminals:
                    continue

                beta = rhs[idx + 1 :]
                first_beta = first_of_sequence(beta, first_sets)
                before = set(follow_sets[symbol])

                follow_sets[symbol] |= {t for t in first_beta if t != EPSILON}
                if not beta or EPSILON in first_beta:
                    follow_sets[symbol] |= follow_sets[prod.lhs]

                if follow_sets[symbol] != before:
                    changed = True

    return follow_sets


def compute_nullable_nonterminals(grammar) -> set[str]:
    nullable: set[str] = set()

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            if prod.lhs in nullable:
                continue
            if not prod.rhs:
                nullable.add(prod.lhs)
                changed = True
                continue
            if all(sym in grammar.nonterminals and sym in nullable for sym in prod.rhs):
                nullable.add(prod.lhs)
                changed = True

    return nullable


def sets_to_json(sets: dict[str, set[str]], keys: set[str] | None = None) -> dict[str, list[str]]:
    if keys is None:
        keys = set(sets.keys())
    return {k: sorted(sets.get(k, set())) for k in sorted(keys)}

