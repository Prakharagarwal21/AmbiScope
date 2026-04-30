#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from http.server import SimpleHTTPRequestHandler
from socketserver import ThreadingTCPServer

from ambiscope.first_follow import compute_first_sets, compute_follow_sets, sets_to_json
from ambiscope.grammar import grammar_to_json, parse_grammar
from ambiscope.ll1 import build_ll1_parse_table, detect_left_recursion
from ambiscope.lr import (
    build_clr1,
    build_lalr1,
    build_lr0,
    build_slr1,
    lr_state_items_to_json,
    lr_tables_to_json,
)
from ambiscope.simulate import simulate_ll1, simulate_lr, tokenize_input
from ambiscope.tree import node_to_json


def production_to_text(grammar, production_id: int) -> str:
    prod = grammar.productions[int(production_id)]
    rhs = " ".join(prod.rhs) if prod.rhs else "ε"
    return f"{prod.lhs} → {rhs}"


def action_to_short_text(action: dict) -> str:
    if action.get("type") == "shift":
        return f"s{action.get('to')}"
    if action.get("type") == "reduce":
        return f"r{action.get('production')}"
    if action.get("type") == "accept":
        return "acc"
    return "?"


def json_response(handler: SimpleHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)

def read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length_raw = handler.headers.get("Content-Length", "0")
    try:
        length = int(length_raw)
    except ValueError as exc:
        raise ValueError("Invalid Content-Length.") from exc
    body = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON body.") from exc

def analyze_payload(payload: dict) -> dict:
    grammar_text = payload.get("grammar", "")
    start_symbol = payload.get("startSymbol", "") or ""
    parser_kind = payload.get("parserKind", "ll1")

    grammar = parse_grammar(grammar_text, start_symbol_override=start_symbol)
    first_sets = compute_first_sets(grammar)
    follow_sets = compute_follow_sets(grammar, first_sets)

    warnings: list[dict] = []
    response: dict = {
        "parserKind": parser_kind,
        "grammar": grammar_to_json(grammar),
        "firstSets": sets_to_json(first_sets, keys=grammar.nonterminals),
        "followSets": sets_to_json(follow_sets, keys=grammar.nonterminals),
        "hasBlockingConflicts": False,
        "warnings": warnings,
    }

    if parser_kind == "ll1":
        ll1 = build_ll1_parse_table(grammar, first_sets, follow_sets)
        left_recursive = detect_left_recursion(grammar)

        if left_recursive:
            warnings.append(
                {
                    "level": "warn",
                    "message": "Left recursion detected",
                    "details": left_recursive,
                }
            )

        if ll1["conflicts"]:
            warnings.append(
                {
                    "level": "warn",
                    "message": f"LL(1) table has {len(ll1['conflicts'])} conflict(s).",
                }
            )
            for c in ll1["conflicts"][:8]:
                warnings.append(
                    {
                        "level": "warn",
                        "message": f"Conflict at [{c['nonterminal']}, {c['terminal']}]",
                        "details": [
                            production_to_text(grammar, c["existingProduction"]),
                            production_to_text(grammar, c["incomingProduction"]),
                        ],
                    }
                )
            if len(ll1["conflicts"]) > 8:
                warnings.append(
                    {
                        "level": "warn",
                        "message": f"({len(ll1['conflicts']) - 8} more LL(1) conflicts not shown)",
                    }
                )
            response["hasBlockingConflicts"] = True
        else:
            warnings.append({"level": "ok", "message": "No LL(1) table conflicts detected."})

        response["ll1"] = {
            "table": ll1["table"],
            "conflicts": ll1["conflicts"],
            "leftRecursion": left_recursive,
        }
        return response

    if parser_kind == "lr0":
        lr = build_lr0(grammar)
    elif parser_kind == "slr1":
        lr = build_slr1(grammar)
    elif parser_kind == "lalr1":
        lr = build_lalr1(grammar)
    elif parser_kind == "clr1":
        lr = build_clr1(grammar)
    else:
        raise ValueError(f"Unknown parserKind '{parser_kind}'.")

    conflicts = lr.get("conflicts", [])
    if conflicts:
        warnings.append(
            {
                "level": "warn",
                "message": f"ACTION/GOTO table has {len(conflicts)} conflict(s).",
            }
        )
        for c in conflicts[:8]:
            if c.get("type") == "action":
                acts = c.get("actions", [])
                actions_text = " / ".join(action_to_short_text(a) for a in acts)
                warnings.append(
                    {
                        "level": "warn",
                        "message": f"State {c.get('state')} on '{c.get('symbol')}': {actions_text}",
                    }
                )
            elif c.get("type") == "goto":
                targets = c.get("targets", [])
                warnings.append(
                    {
                        "level": "warn",
                        "message": f"State {c.get('state')} on '{c.get('symbol')}': multiple GOTO targets {targets}",
                    }
                )
        if len(conflicts) > 8:
            warnings.append(
                {
                    "level": "warn",
                    "message": f"({len(conflicts) - 8} more LR conflicts not shown)",
                }
            )
        response["hasBlockingConflicts"] = True
    else:
        warnings.append({"level": "ok", "message": "No ACTION/GOTO table conflicts detected."})

    kind = lr["kind"]
    states_json = lr_state_items_to_json(kind, lr["grammar"], lr["states"])
    tables_json = lr_tables_to_json(lr["actionTable"], lr["gotoTable"], lr["conflicts"])

    response["lr"] = {
        "kind": kind,
        "grammar": grammar_to_json(lr["grammar"]),
        "states": states_json,
        **tables_json,
    }

    return response


def simulate_payload(payload: dict) -> dict:
    grammar_text = payload.get("grammar", "")
    start_symbol = payload.get("startSymbol", "") or ""
    parser_kind = payload.get("parserKind", "ll1")
    input_raw = payload.get("input", "") or ""

    grammar = parse_grammar(grammar_text, start_symbol_override=start_symbol)

    if parser_kind == "ll1":
        first_sets = compute_first_sets(grammar)
        follow_sets = compute_follow_sets(grammar, first_sets)
        ll1 = build_ll1_parse_table(grammar, first_sets, follow_sets)
        if ll1["conflicts"]:
            raise ValueError("Cannot simulate: LL(1) table conflicts exist.")

        tokens = tokenize_input(input_raw, terminals=grammar.terminals)
        sim = simulate_ll1(grammar, ll1["table"], tokens)
        return simulation_to_json(sim)

    if parser_kind == "lr0":
        lr = build_lr0(grammar)
    elif parser_kind == "slr1":
        lr = build_slr1(grammar)
    elif parser_kind == "lalr1":
        lr = build_lalr1(grammar)
    elif parser_kind == "clr1":
        lr = build_clr1(grammar)
    else:
        raise ValueError(f"Unknown parserKind '{parser_kind}'.")

    if lr.get("conflicts"):
        raise ValueError("Cannot simulate: ACTION/GOTO conflicts exist for this parser.")

    tokens = tokenize_input(input_raw, terminals=lr["grammar"].terminals)
    sim = simulate_lr(lr["grammar"], lr["actionTable"], lr["gotoTable"], tokens)
    return simulation_to_json(sim)

def simulation_to_json(sim: dict) -> dict:
    steps_out = []
    for s in sim.get("steps", []):
        steps_out.append(
            {
                "stack": s["stack"],
                "input": s["input"],
                "pointer": s["pointer"],
                "action": s["action"],
                "note": s.get("note", ""),
                "tree": node_to_json(s.get("tree")),
            }
        )
    out = {
        "accepted": bool(sim.get("accepted")),
        "steps": steps_out,
    }
    if sim.get("error"):
        out["error"] = sim["error"]
    if sim.get("tree") is not None:
        out["tree"] = node_to_json(sim.get("tree"))
    return out


class AmbiScopeHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:  # noqa: D401
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):  # noqa: N802
        try:
            if self.path == "/api/analyze":
                payload = read_json(self)
                data = analyze_payload(payload)
                return json_response(self, 200, {"ok": True, "analysis": data})

            if self.path == "/api/simulate":
                payload = read_json(self)
                data = simulate_payload(payload)
                return json_response(self, 200, {"ok": True, "simulation": data})

            return json_response(self, 404, {"ok": False, "error": "Not found"})
        except Exception as exc:  # noqa: BLE001
            return json_response(self, 400, {"ok": False, "error": str(exc)})


class ReusableThreadingTCPServer(ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description="AmbiScope local server (static UI + Python parser backend).")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    with ReusableThreadingTCPServer((args.host, args.port), AmbiScopeHandler) as httpd:
        print(f"AmbiScope running on http://{args.host}:{args.port}")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
