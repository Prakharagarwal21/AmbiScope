import unittest
from pathlib import Path

from ambiscope.first_follow import compute_first_sets, compute_follow_sets
from ambiscope.grammar import parse_grammar
from ambiscope.ll1 import build_ll1_parse_table
from ambiscope.lr import build_clr1, build_lalr1, build_lr0, build_slr1
from ambiscope.simulate import simulate_ll1, simulate_lr, tokenize_input


def read_example(name: str) -> str:
    root = Path(__file__).resolve().parent.parent
    return (root / "examples" / name).read_text(encoding="utf-8")


class TestLL1(unittest.TestCase):
    def test_ll1_expression_accepts(self) -> None:
        grammar = parse_grammar(read_example("ll1_expression.txt"))
        first_sets = compute_first_sets(grammar)
        follow_sets = compute_follow_sets(grammar, first_sets)
        ll1 = build_ll1_parse_table(grammar, first_sets, follow_sets)
        self.assertEqual(len(ll1["conflicts"]), 0)

        tokens = tokenize_input("id + id * id", terminals=grammar.terminals)
        sim = simulate_ll1(grammar, ll1["table"], tokens)
        self.assertTrue(sim["accepted"])
        self.assertGreater(len(sim["steps"]), 0)
        self.assertIsNotNone(sim["steps"][-1].get("tree"))


class TestLR(unittest.TestCase):
    def test_lr0_cc_accepts(self) -> None:
        grammar = parse_grammar(read_example("lr0_cc.txt"))
        lr0 = build_lr0(grammar)
        self.assertEqual(len(lr0["conflicts"]), 0)

        sim = simulate_lr(lr0["grammar"], lr0["actionTable"], lr0["gotoTable"], ["c", "d", "d"])
        self.assertTrue(sim["accepted"])

    def test_expression_is_not_lr0_but_is_slr_lalr_clr(self) -> None:
        grammar = parse_grammar(read_example("ll1_expression.txt"))

        lr0 = build_lr0(grammar)
        self.assertGreater(len(lr0["conflicts"]), 0)

        slr = build_slr1(grammar)
        self.assertEqual(len(slr["conflicts"]), 0)
        sim_slr = simulate_lr(slr["grammar"], slr["actionTable"], slr["gotoTable"], ["id", "+", "id", "*", "id"])
        self.assertTrue(sim_slr["accepted"])

        lalr = build_lalr1(grammar)
        self.assertEqual(len(lalr["conflicts"]), 0)
        sim_lalr = simulate_lr(
            lalr["grammar"], lalr["actionTable"], lalr["gotoTable"], ["id", "+", "id", "*", "id"]
        )
        self.assertTrue(sim_lalr["accepted"])

        clr = build_clr1(grammar)
        self.assertEqual(len(clr["conflicts"]), 0)
        sim_clr = simulate_lr(clr["grammar"], clr["actionTable"], clr["gotoTable"], ["id", "+", "id", "*", "id"])
        self.assertTrue(sim_clr["accepted"])

    def test_lalr_not_slr_example(self) -> None:
        grammar = parse_grammar(read_example("lalr_not_slr.txt"))
        slr = build_slr1(grammar)
        self.assertGreater(len(slr["conflicts"]), 0)

        lalr = build_lalr1(grammar)
        self.assertEqual(len(lalr["conflicts"]), 0)

        clr = build_clr1(grammar)
        self.assertEqual(len(clr["conflicts"]), 0)

    def test_clr_not_lalr_example(self) -> None:
        grammar = parse_grammar(read_example("clr_not_lalr.txt"))
        clr = build_clr1(grammar)
        self.assertEqual(len(clr["conflicts"]), 0)

        lalr = build_lalr1(grammar)
        self.assertGreater(len(lalr["conflicts"]), 0)

    def test_dangling_else_has_conflict(self) -> None:
        grammar = parse_grammar(read_example("dangling_else.txt"))
        slr = build_slr1(grammar)
        self.assertGreater(len(slr["conflicts"]), 0)

        lalr = build_lalr1(grammar)
        self.assertGreater(len(lalr["conflicts"]), 0)

        clr = build_clr1(grammar)
        self.assertGreater(len(clr["conflicts"]), 0)


if __name__ == "__main__":
    unittest.main()

