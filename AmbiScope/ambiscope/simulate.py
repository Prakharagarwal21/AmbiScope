from __future__ import annotations

from .constants import ENDMARKER, EPSILON
from .tree import ParseNode, clone_tree


def tokenize_input(raw: str, terminals: set[str] | None = None) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []
    if any(ch.isspace() for ch in text):
        return [t for t in text.split() if t]
    terminals = terminals or set()
    all_single = bool(terminals) and all(len(t) == 1 for t in terminals)
    if all_single:
        return list(text)
    return [text]


def _fmt_prod(grammar, production_id: int) -> str:
    prod = grammar.productions[production_id]
    rhs = " ".join(prod.rhs) if prod.rhs else EPSILON
    return f"{prod.lhs} → {rhs}"


def _normalize_tree_for_display(grammar, node: ParseNode | None) -> ParseNode | None:
    if node is None:
        return None
    if grammar.original_start_symbol and node.symbol == grammar.start_symbol and len(node.children) == 1:
        child = node.children[0]
        if child.symbol == grammar.original_start_symbol:
            return child
    return node


def simulate_ll1(grammar, parse_table: dict[str, dict[str, int]], input_tokens: list[str]):
    tokens = list(input_tokens) + [ENDMARKER]
    symbol_stack: list[str] = [ENDMARKER, grammar.start_symbol]

    root = ParseNode(grammar.start_symbol)
    node_stack: list[ParseNode] = [ParseNode(ENDMARKER), root]

    steps: list[dict] = []
    pointer = 0

    def snapshot(action: str, note: str = ""):
        steps.append(
            {
                "stack": list(symbol_stack),
                "input": list(tokens),
                "pointer": pointer,
                "action": action,
                "note": note,
                "tree": clone_tree(root),
            }
        )

    snapshot("init")

    while symbol_stack:
        top = symbol_stack[-1]
        current = tokens[pointer] if pointer < len(tokens) else ENDMARKER

        if top == ENDMARKER and current == ENDMARKER:
            snapshot("accept")
            return {"accepted": True, "steps": steps, "tree": root}

        if top == ENDMARKER:
            snapshot("error", f"Unexpected end of stack. Expected {current}.")
            return {"accepted": False, "steps": steps, "tree": root, "error": "Unexpected end of stack."}

        is_nonterminal = top in grammar.nonterminals
        if not is_nonterminal:
            if top == current:
                symbol_stack.pop()
                node_stack.pop()
                pointer += 1
                snapshot(f"match {current}")
                continue
            snapshot("error", f"Mismatch: stack has '{top}' but input has '{current}'.")
            return {"accepted": False, "steps": steps, "tree": root, "error": "Mismatch."}

        row = parse_table.get(top, {})
        production_id = row.get(current)
        if production_id is None:
            snapshot("error", f"No table entry for [{top}, {current}]")
            return {"accepted": False, "steps": steps, "tree": root, "error": "No table entry."}

        prod = grammar.productions[production_id]
        symbol_stack.pop()
        parent = node_stack.pop()

        if not prod.rhs:
            parent.children.append(ParseNode(EPSILON))
            snapshot(_fmt_prod(grammar, production_id))
            continue

        children = [ParseNode(sym) for sym in prod.rhs]
        parent.children.extend(children)
        for sym, child in reversed(list(zip(prod.rhs, children))):
            symbol_stack.append(sym)
            node_stack.append(child)

        snapshot(_fmt_prod(grammar, production_id))

    snapshot("error", "Stack emptied without accepting.")
    return {"accepted": False, "steps": steps, "tree": root, "error": "Stack emptied."}


def simulate_lr(grammar, action_table, goto_table, input_tokens: list[str], max_steps: int = 5000):
    tokens = list(input_tokens) + [ENDMARKER]
    state_stack: list[int] = [0]
    node_stack: list[ParseNode] = []
    pointer = 0
    steps: list[dict] = []

    def snapshot(action: str, note: str = ""):
        pairs = []
        for idx, st in enumerate(state_stack):
            if idx == 0:
                pairs.append({"state": st, "symbol": ""})
            else:
                pairs.append({"state": st, "symbol": node_stack[idx - 1].symbol if idx - 1 < len(node_stack) else ""})

        top_tree = node_stack[-1] if node_stack else None
        steps.append(
            {
                "stack": pairs,
                "input": list(tokens),
                "pointer": pointer,
                "action": action,
                "note": note,
                "tree": clone_tree(_normalize_tree_for_display(grammar, top_tree)),
            }
        )

    def action_to_text(action) -> str:
        kind, value = action
        if kind == "shift":
            return f"shift {int(value)}"
        if kind == "reduce":
            return f"reduce {_fmt_prod(grammar, int(value))}"
        if kind == "accept":
            return "accept"
        return "error"

    snapshot("init")

    guard = 0
    while guard < max_steps:
        guard += 1
        state = state_stack[-1]
        lookahead = tokens[pointer] if pointer < len(tokens) else ENDMARKER

        cell = action_table.get(state, {}).get(lookahead, [])
        if len(cell) != 1:
            snapshot("error", "No ACTION entry." if len(cell) == 0 else "Conflict in ACTION table.")
            return {
                "accepted": False,
                "steps": steps,
                "error": "No ACTION entry." if len(cell) == 0 else "Conflict in ACTION table.",
            }

        act = cell[0]
        if act[0] == "shift":
            node_stack.append(ParseNode(lookahead))
            state_stack.append(int(act[1]))
            pointer += 1
            snapshot(action_to_text(act))
            continue

        if act[0] == "reduce":
            prod_id = int(act[1])
            prod = grammar.productions[prod_id]
            pop_count = len(prod.rhs)

            children: list[ParseNode] = []
            for _ in range(pop_count):
                state_stack.pop()
                children.insert(0, node_stack.pop())
            if pop_count == 0:
                children.append(ParseNode(EPSILON))

            node = ParseNode(prod.lhs, children)
            top_state = state_stack[-1]
            goto_state = goto_table.get(top_state, {}).get(prod.lhs)
            if goto_state is None:
                snapshot("error", f"Missing GOTO[{top_state}, {prod.lhs}]")
                return {"accepted": False, "steps": steps, "error": "Missing GOTO entry."}

            node_stack.append(node)
            state_stack.append(int(goto_state))
            snapshot(action_to_text(act))
            continue

        if act[0] == "accept":
            snapshot("accept")
            root = node_stack[-1] if node_stack else None
            root = _normalize_tree_for_display(grammar, root)
            return {"accepted": True, "steps": steps, "tree": root}

        snapshot("error", "Unknown parser action.")
        return {"accepted": False, "steps": steps, "error": "Unknown parser action."}

    snapshot("error", "Step limit exceeded.")
    return {"accepted": False, "steps": steps, "error": "Step limit exceeded."}
