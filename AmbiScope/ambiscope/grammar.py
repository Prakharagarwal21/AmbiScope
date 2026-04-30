from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .constants import EPSILON
from .util import normalize_arrow, normalize_whitespace, strip_inline_comment, unique_name


@dataclass(frozen=True)
class Production:
    id: int
    lhs: str
    rhs: tuple[str, ...]


@dataclass
class Grammar:
    start_symbol: str
    terminals: set[str]
    nonterminals: set[str]
    productions: list[Production]
    productions_by_lhs: dict[str, list[Production]]
    all_symbols: set[str]
    original_start_symbol: Optional[str] = None


def _is_epsilon_token(token: str) -> bool:
    if not token:
        return False
    normalized = token.strip().lower()
    return normalized in {EPSILON, "epsilon", "eps", "λ", "lambda"}


def parse_grammar(grammar_text: str, start_symbol_override: str | None = None) -> Grammar:
    raw_lines = str(grammar_text).splitlines()
    productions: list[Production] = []

    for raw_line in raw_lines:
        cleaned = normalize_whitespace(strip_inline_comment(normalize_arrow(raw_line)))
        if not cleaned:
            continue

        parts = cleaned.split("->")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid production (missing '->'): {raw_line}. "
                "Tip: the Grammar box must contain productions like `A -> ...`. "
                "Put the test input (e.g. `id + id * id`) in the Input String field."
            )

        lhs = normalize_whitespace(parts[0])
        if not lhs:
            raise ValueError(f"Invalid production (empty LHS): {raw_line}")
        if " " in lhs:
            raise ValueError(f"Invalid production (LHS must be a single symbol): {raw_line}")

        rhs_part = normalize_whitespace(parts[1])
        if not rhs_part:
            productions.append(Production(id=len(productions), lhs=lhs, rhs=()))
            continue

        for alt in (normalize_whitespace(a) for a in rhs_part.split("|")):
            if not alt:
                productions.append(Production(id=len(productions), lhs=lhs, rhs=()))
                continue
            if _is_epsilon_token(alt):
                productions.append(Production(id=len(productions), lhs=lhs, rhs=()))
                continue

            symbols = [s for s in alt.split(" ") if s]
            eps_tokens = [s for s in symbols if _is_epsilon_token(s)]
            if eps_tokens:
                raise ValueError(
                    f"Epsilon (ε) must be alone in a production alternative. Problem line: {raw_line}"
                )
            productions.append(Production(id=len(productions), lhs=lhs, rhs=tuple(symbols)))

    if not productions:
        raise ValueError("Grammar is empty.")

    nonterminals = {p.lhs for p in productions}
    terminals: set[str] = set()
    for p in productions:
        for sym in p.rhs:
            if sym not in nonterminals:
                terminals.add(sym)

    start_symbol = (start_symbol_override or "").strip() or productions[0].lhs
    if start_symbol not in nonterminals:
        raise ValueError(f"Start symbol '{start_symbol}' is not a nonterminal in the grammar.")

    productions_by_lhs: dict[str, list[Production]] = {}
    for p in productions:
        productions_by_lhs.setdefault(p.lhs, []).append(p)

    all_symbols = set(nonterminals) | set(terminals)

    return Grammar(
        start_symbol=start_symbol,
        terminals=terminals,
        nonterminals=nonterminals,
        productions=productions,
        productions_by_lhs=productions_by_lhs,
        all_symbols=all_symbols,
        original_start_symbol=None,
    )


def augment_grammar(grammar: Grammar) -> Grammar:
    used = set(grammar.all_symbols)
    augmented_start = unique_name(f"{grammar.start_symbol}'", used)

    productions: list[Production] = []
    productions.append(Production(id=0, lhs=augmented_start, rhs=(grammar.start_symbol,)))
    for old in grammar.productions:
        productions.append(Production(id=len(productions), lhs=old.lhs, rhs=old.rhs))

    nonterminals = set(grammar.nonterminals) | {augmented_start}
    terminals = set(grammar.terminals)

    productions_by_lhs: dict[str, list[Production]] = {}
    for p in productions:
        productions_by_lhs.setdefault(p.lhs, []).append(p)

    all_symbols = set(nonterminals) | set(terminals)

    return Grammar(
        start_symbol=augmented_start,
        terminals=terminals,
        nonterminals=nonterminals,
        productions=productions,
        productions_by_lhs=productions_by_lhs,
        all_symbols=all_symbols,
        original_start_symbol=grammar.start_symbol,
    )


def grammar_to_json(grammar: Grammar) -> dict:
    return {
        "startSymbol": grammar.start_symbol,
        "originalStartSymbol": grammar.original_start_symbol,
        "terminals": sorted(grammar.terminals),
        "nonterminals": sorted(grammar.nonterminals),
        "productions": [
            {"id": p.id, "lhs": p.lhs, "rhs": list(p.rhs)} for p in grammar.productions
        ],
    }
