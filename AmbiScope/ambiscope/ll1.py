from __future__ import annotations
from .constants import EPSILON
from .first_follow import compute_nullable_nonterminals, first_of_sequence

def build_ll1_parse_table(grammar, first_sets, follow_sets):
    table: dict[str, dict[str, int]] = {nt: {} for nt in grammar.nonterminals}
    conflicts: list[dict] = []

    for prod in grammar.productions:
        first_alpha = first_of_sequence(list(prod.rhs), first_sets)
        for terminal in sorted(t for t in first_alpha if t != EPSILON):
            existing = table[prod.lhs].get(terminal)
            if existing is not None and existing != prod.id:
                conflicts.append(
                    {
                        "nonterminal": prod.lhs,
                        "terminal": terminal,
                        "existingProduction": existing,
                        "incomingProduction": prod.id,
                    }
                )
            else:
                table[prod.lhs][terminal] = prod.id

        if EPSILON in first_alpha:
            for terminal in sorted(follow_sets.get(prod.lhs, set())):
                existing = table[prod.lhs].get(terminal)
                if existing is not None and existing != prod.id:
                    conflicts.append(
                        {
                            "nonterminal": prod.lhs,
                            "terminal": terminal,
                            "existingProduction": existing,
                            "incomingProduction": prod.id,
                        }
                    )
                else:
                    table[prod.lhs][terminal] = prod.id

    return {"table": table, "conflicts": conflicts}


def detect_left_recursion(grammar) -> list[str]:
    nullable = compute_nullable_nonterminals(grammar)
    edges: dict[str, set[str]] = {nt: set() for nt in grammar.nonterminals}

    for prod in grammar.productions:
        rhs = list(prod.rhs)
        for sym in rhs:
            if sym in grammar.nonterminals:
                edges[prod.lhs].add(sym)
            else:
                break
            if sym not in nullable:
                break

    left_recursive: set[str] = set()
    for start in grammar.nonterminals:
        visited: set[str] = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            for nxt in edges.get(current, set()):
                if nxt == start:
                    left_recursive.add(start)
                    stack.clear()
                    break
                stack.append(nxt)

    return sorted(left_recursive)

