# AmbiScope

AmbiScope is a web-based, interactive compiler-design visualization tool for context‑free grammars (CFGs).

Parser logic is implemented in **Python** (table construction + simulation), and the UI is built with **HTML/CSS/JS**.

It helps you:

- Analyze a CFG for parser suitability
- Build parsing tables for multiple algorithms
- Visualize step-by-step parsing (stack, input buffer, actions)
- See a live parse-tree view during the run

Supported parsers:

- **LL(1)** (top‑down)
- **LR(0)**, **SLR(1)**, **LALR(1)**, **CLR(1)** (bottom‑up)

## Run locally

AmbiScope uses a small local Python server for all parser logic (tables + simulation) and serves the frontend UI.

```bash
python3 server.py --port 8000
```

Then open `http://localhost:8000` in your browser.

## Grammar format

- One production per line: `A -> α | β`
- **LHS must be a single nonterminal symbol**
- Separate symbols by spaces
- Use **`ε`** for empty productions
- Use **`$`** is automatic end‑marker (you do not type it)

Example (LL(1) expression grammar):

```txt
E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id
```

Input example:

```txt
id + id * id
```

## Examples

Sample grammars are included in `examples/`:

- `examples/ll1_expression.txt` – LL(1) + LR family friendly
- `examples/lr0_cc.txt` – a small LR(0) grammar
- `examples/left_recursive_expr.txt` – triggers LL(1) issues (left recursion)
- `examples/dangling_else.txt` – classic ambiguity / shift‑reduce conflict example
- `examples/lalr_not_slr.txt` – SLR(1) conflict, but LALR(1)/CLR(1) works
- `examples/clr_not_lalr.txt` – CLR(1) works, but LALR(1) conflicts (state merge issue)

## Validate (tests)

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
```

## Notes / limitations

- Tokens are expected to be **space-separated** in both grammar RHS and input string.
- General ambiguity detection for CFGs is not fully decidable; AmbiScope focuses on practical signals:
  - **LL(1) table conflicts**
  - **LR shift/reduce or reduce/reduce conflicts**
