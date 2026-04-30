from __future__ import annotations

from dataclasses import dataclass

from .constants import ENDMARKER, EPSILON
from .first_follow import compute_first_sets, compute_follow_sets, first_of_sequence
from .grammar import Grammar, augment_grammar


Action = tuple[str, int | None]  # ("shift", state) | ("reduce", prod_id) | ("accept", None)


def _add_action_cell(
    action_table: dict[int, dict[str, list[Action]]],
    conflicts: list[dict],
    state: int,
    terminal: str,
    action: Action,
) -> None:
    row = action_table.setdefault(state, {})
    cell = row.setdefault(terminal, [])
    if action in cell:
        return
    cell.append(action)
    if len(cell) == 2:
        conflicts.append(
            {
                "type": "action",
                "state": state,
                "symbol": terminal,
                "actions": [action_to_json(a) for a in cell],
            }
        )


def _set_goto_cell(
    goto_table: dict[int, dict[str, int]],
    conflicts: list[dict],
    state: int,
    nonterminal: str,
    to_state: int,
) -> None:
    row = goto_table.setdefault(state, {})
    existing = row.get(nonterminal)
    if existing is not None and existing != to_state:
        conflicts.append(
            {
                "type": "goto",
                "state": state,
                "symbol": nonterminal,
                "targets": [existing, to_state],
            }
        )
    row[nonterminal] = to_state


def action_to_json(action: Action) -> dict:
    kind, value = action
    if kind == "shift":
        return {"type": "shift", "to": int(value)}
    if kind == "reduce":
        return {"type": "reduce", "production": int(value)}
    if kind == "accept":
        return {"type": "accept"}
    return {"type": "error"}


def closure_lr0(items: set[tuple[int, int]], grammar: Grammar) -> frozenset[tuple[int, int]]:
    closure: set[tuple[int, int]] = set(items)
    queue = list(items)

    while queue:
        production_id, dot = queue.pop()
        prod = grammar.productions[production_id]
        if dot >= len(prod.rhs):
            continue
        nxt = prod.rhs[dot]
        if nxt not in grammar.nonterminals:
            continue

        for p in grammar.productions_by_lhs.get(nxt, []):
            next_item = (p.id, 0)
            if next_item not in closure:
                closure.add(next_item)
                queue.append(next_item)

    return frozenset(closure)


def goto_lr0(
    state_items: frozenset[tuple[int, int]], symbol: str, grammar: Grammar
) -> frozenset[tuple[int, int]]:
    moved: set[tuple[int, int]] = set()
    for production_id, dot in state_items:
        prod = grammar.productions[production_id]
        if dot < len(prod.rhs) and prod.rhs[dot] == symbol:
            moved.add((production_id, dot + 1))
    if not moved:
        return frozenset()
    return closure_lr0(moved, grammar)


def build_lr0_automaton(grammar: Grammar):
    symbols = sorted(list(grammar.terminals | grammar.nonterminals))
    start_state = closure_lr0({(0, 0)}, grammar)

    states: list[frozenset[tuple[int, int]]] = [start_state]
    state_map: dict[frozenset[tuple[int, int]], int] = {start_state: 0}
    transitions: list[dict[str, int]] = [{}]

    queue = [0]
    while queue:
        from_state = queue.pop(0)
        from_items = states[from_state]
        trans: dict[str, int] = {}

        for sym in symbols:
            target = goto_lr0(from_items, sym, grammar)
            if not target:
                continue
            to_state = state_map.get(target)
            if to_state is None:
                to_state = len(states)
                states.append(target)
                state_map[target] = to_state
                transitions.append({})
                queue.append(to_state)
            trans[sym] = to_state

        transitions[from_state] = trans

    return {"states": states, "transitions": transitions}


def build_lr_table_from_lr0_automaton(grammar: Grammar, automaton, reduce_lookaheads_fn):
    action_table: dict[int, dict[str, list[Action]]] = {}
    goto_table: dict[int, dict[str, int]] = {}
    conflicts: list[dict] = []
    terminals = sorted(list(grammar.terminals | {ENDMARKER}))

    for state_id, items in enumerate(automaton["states"]):
        trans = automaton["transitions"][state_id]

        for production_id, dot in items:
            prod = grammar.productions[production_id]

            if dot < len(prod.rhs):
                nxt = prod.rhs[dot]
                if nxt in grammar.terminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _add_action_cell(action_table, conflicts, state_id, nxt, ("shift", to_state))
                elif nxt in grammar.nonterminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _set_goto_cell(goto_table, conflicts, state_id, nxt, to_state)
                continue

            if production_id == 0:
                _add_action_cell(action_table, conflicts, state_id, ENDMARKER, ("accept", None))
                continue

            for la in reduce_lookaheads_fn(grammar, production_id, terminals):
                _add_action_cell(action_table, conflicts, state_id, la, ("reduce", production_id))

        for nt in grammar.nonterminals:
            to_state = trans.get(nt)
            if to_state is not None:
                _set_goto_cell(goto_table, conflicts, state_id, nt, to_state)

    return {"actionTable": action_table, "gotoTable": goto_table, "conflicts": conflicts}


def build_lr0(original_grammar: Grammar):
    grammar = augment_grammar(original_grammar)
    automaton = build_lr0_automaton(grammar)
    tables = build_lr_table_from_lr0_automaton(
        grammar,
        automaton,
        reduce_lookaheads_fn=lambda g, production_id, terminals: terminals,
    )
    return {"kind": "lr0", "grammar": grammar, **automaton, **tables}


def build_slr1(original_grammar: Grammar):
    grammar = augment_grammar(original_grammar)
    first_sets = compute_first_sets(grammar)
    follow_sets = compute_follow_sets(grammar, first_sets)
    automaton = build_lr0_automaton(grammar)

    def lookaheads(g: Grammar, production_id: int, _terminals: list[str]):
        lhs = g.productions[production_id].lhs
        return sorted(list(follow_sets.get(lhs, set())))

    tables = build_lr_table_from_lr0_automaton(grammar, automaton, reduce_lookaheads_fn=lookaheads)
    return {
        "kind": "slr1",
        "grammar": grammar,
        "firstSets": first_sets,
        "followSets": follow_sets,
        **automaton,
        **tables,
    }


def closure_lr1(items: set[tuple[int, int, str]], grammar: Grammar, first_sets) -> frozenset[tuple[int, int, str]]:
    closure: set[tuple[int, int, str]] = set(items)
    queue = list(items)

    while queue:
        production_id, dot, lookahead = queue.pop()
        prod = grammar.productions[production_id]
        if dot >= len(prod.rhs):
            continue
        nxt = prod.rhs[dot]
        if nxt not in grammar.nonterminals:
            continue

        beta = list(prod.rhs[dot + 1 :])
        lookahead_seq = beta + [lookahead]
        las = first_of_sequence(lookahead_seq, first_sets)
        las.discard(EPSILON)

        for p in grammar.productions_by_lhs.get(nxt, []):
            for la in las:
                next_item = (p.id, 0, la)
                if next_item not in closure:
                    closure.add(next_item)
                    queue.append(next_item)

    return frozenset(closure)


def goto_lr1(
    state_items: frozenset[tuple[int, int, str]], symbol: str, grammar: Grammar, first_sets
) -> frozenset[tuple[int, int, str]]:
    moved: set[tuple[int, int, str]] = set()
    for production_id, dot, lookahead in state_items:
        prod = grammar.productions[production_id]
        if dot < len(prod.rhs) and prod.rhs[dot] == symbol:
            moved.add((production_id, dot + 1, lookahead))
    if not moved:
        return frozenset()
    return closure_lr1(moved, grammar, first_sets)


def build_lr1_automaton(grammar: Grammar, first_sets):
    symbols = sorted(list(grammar.terminals | grammar.nonterminals))
    start_state = closure_lr1({(0, 0, ENDMARKER)}, grammar, first_sets)

    states: list[frozenset[tuple[int, int, str]]] = [start_state]
    state_map: dict[frozenset[tuple[int, int, str]], int] = {start_state: 0}
    transitions: list[dict[str, int]] = [{}]

    queue = [0]
    while queue:
        from_state = queue.pop(0)
        from_items = states[from_state]
        trans: dict[str, int] = {}

        for sym in symbols:
            target = goto_lr1(from_items, sym, grammar, first_sets)
            if not target:
                continue
            to_state = state_map.get(target)
            if to_state is None:
                to_state = len(states)
                states.append(target)
                state_map[target] = to_state
                transitions.append({})
                queue.append(to_state)
            trans[sym] = to_state

        transitions[from_state] = trans

    return {"states": states, "transitions": transitions}


def build_clr1(original_grammar: Grammar):
    grammar = augment_grammar(original_grammar)
    first_sets = compute_first_sets(grammar)
    automaton = build_lr1_automaton(grammar, first_sets)

    action_table: dict[int, dict[str, list[Action]]] = {}
    goto_table: dict[int, dict[str, int]] = {}
    conflicts: list[dict] = []

    for state_id, items in enumerate(automaton["states"]):
        trans = automaton["transitions"][state_id]

        for production_id, dot, lookahead in items:
            prod = grammar.productions[production_id]

            if dot < len(prod.rhs):
                nxt = prod.rhs[dot]
                if nxt in grammar.terminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _add_action_cell(action_table, conflicts, state_id, nxt, ("shift", to_state))
                elif nxt in grammar.nonterminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _set_goto_cell(goto_table, conflicts, state_id, nxt, to_state)
                continue

            if production_id == 0 and lookahead == ENDMARKER:
                _add_action_cell(action_table, conflicts, state_id, ENDMARKER, ("accept", None))
                continue

            _add_action_cell(action_table, conflicts, state_id, lookahead, ("reduce", production_id))

        for nt in grammar.nonterminals:
            to_state = trans.get(nt)
            if to_state is not None:
                _set_goto_cell(goto_table, conflicts, state_id, nt, to_state)

    return {
        "kind": "clr1",
        "grammar": grammar,
        "firstSets": first_sets,
        **automaton,
        "actionTable": action_table,
        "gotoTable": goto_table,
        "conflicts": conflicts,
    }


def build_lalr1(original_grammar: Grammar):
    grammar = augment_grammar(original_grammar)
    first_sets = compute_first_sets(grammar)
    lr1 = build_lr1_automaton(grammar, first_sets)

    def core_signature(state_items: frozenset[tuple[int, int, str]]):
        return frozenset((prod_id, dot) for (prod_id, dot, _la) in state_items)

    core_to_merged: dict[frozenset[tuple[int, int]], int] = {}
    merged_for_state: list[int] = [0 for _ in lr1["states"]]
    merged_items: list[dict[tuple[int, int], set[str]]] = []
    merged_transitions: list[dict[str, int]] = []

    for state_id, items in enumerate(lr1["states"]):
        core = core_signature(items)
        merged_id = core_to_merged.get(core)
        if merged_id is None:
            merged_id = len(merged_items)
            core_to_merged[core] = merged_id
            merged_items.append({})
            merged_transitions.append({})
        merged_for_state[state_id] = merged_id

        store = merged_items[merged_id]
        for prod_id, dot, la in items:
            store.setdefault((prod_id, dot), set()).add(la)

    for from_state, trans in enumerate(lr1["transitions"]):
        from_merged = merged_for_state[from_state]
        for sym, to_state in trans.items():
            to_merged = merged_for_state[to_state]
            merged_transitions[from_merged].setdefault(sym, to_merged)

    action_table: dict[int, dict[str, list[Action]]] = {}
    goto_table: dict[int, dict[str, int]] = {}
    conflicts: list[dict] = []
    terminals = sorted(list(grammar.terminals | {ENDMARKER}))

    for state_id, items in enumerate(merged_items):
        trans = merged_transitions[state_id]
        for (prod_id, dot), lookaheads in items.items():
            prod = grammar.productions[prod_id]

            if dot < len(prod.rhs):
                nxt = prod.rhs[dot]
                if nxt in grammar.terminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _add_action_cell(action_table, conflicts, state_id, nxt, ("shift", to_state))
                elif nxt in grammar.nonterminals:
                    to_state = trans.get(nxt)
                    if to_state is not None:
                        _set_goto_cell(goto_table, conflicts, state_id, nxt, to_state)
                continue

            for la in lookaheads:
                if prod_id == 0 and la == ENDMARKER:
                    _add_action_cell(action_table, conflicts, state_id, ENDMARKER, ("accept", None))
                    continue
                if la in terminals:
                    _add_action_cell(action_table, conflicts, state_id, la, ("reduce", prod_id))

        for nt in grammar.nonterminals:
            to_state = trans.get(nt)
            if to_state is not None:
                _set_goto_cell(goto_table, conflicts, state_id, nt, to_state)

    state_items_for_display: list[list[dict]] = []
    for items in merged_items:
        state_items_for_display.append(
            [
                {"production": prod_id, "dot": dot, "lookaheads": sorted(list(lookaheads))}
                for (prod_id, dot), lookaheads in sorted(items.items(), key=lambda kv: kv[0])
            ]
        )

    return {
        "kind": "lalr1",
        "grammar": grammar,
        "firstSets": first_sets,
        "states": state_items_for_display,
        "transitions": merged_transitions,
        "actionTable": action_table,
        "gotoTable": goto_table,
        "conflicts": conflicts,
    }


def lr_state_items_to_json(kind: str, grammar: Grammar, states) -> list[list[dict]]:
    if kind in {"lr0", "slr1"}:
        result: list[list[dict]] = []
        for items in states:
            result.append(
                [
                    {"production": prod_id, "dot": dot}
                    for (prod_id, dot) in sorted(items, key=lambda x: (x[0], x[1]))
                ]
            )
        return result

    if kind == "clr1":
        result: list[list[dict]] = []
        for items in states:
            result.append(
                [
                    {"production": prod_id, "dot": dot, "lookahead": la}
                    for (prod_id, dot, la) in sorted(items, key=lambda x: (x[0], x[1], x[2]))
                ]
            )
        return result

    if kind == "lalr1":
        return states

    return []


def lr_tables_to_json(action_table, goto_table, conflicts) -> dict:
    action_json: dict[str, dict[str, list[dict]]] = {}
    for state, row in action_table.items():
        action_json[str(state)] = {t: [action_to_json(a) for a in acts] for t, acts in row.items()}

    goto_json: dict[str, dict[str, int]] = {}
    for state, row in goto_table.items():
        goto_json[str(state)] = {nt: int(to) for nt, to in row.items()}

    return {"actionTable": action_json, "gotoTable": goto_json, "conflicts": conflicts}

