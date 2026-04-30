from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParseNode:
    symbol: str
    children: list["ParseNode"] = field(default_factory=list)


def clone_tree(node: ParseNode | None) -> ParseNode | None:
    if node is None:
        return None
    return ParseNode(node.symbol, [clone_tree(c) for c in node.children])


def node_to_json(node: ParseNode | None):
    if node is None:
        return None
    return {"symbol": node.symbol, "children": [node_to_json(c) for c in node.children]}

