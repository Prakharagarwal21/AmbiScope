import { escapeHtml } from "./util.js";

function layoutTree(root) {
  let nextX = 0;
  let maxDepth = 0;
  const positions = new Map();

  function walk(node, depth) {
    maxDepth = Math.max(maxDepth, depth);
    const children = node.children ?? [];
    if (children.length === 0) {
      const x = nextX++;
      positions.set(node, { x, y: depth });
      return x;
    }

    const childXs = children.map((child) => walk(child, depth + 1));
    const x = childXs.reduce((sum, v) => sum + v, 0) / childXs.length;
    positions.set(node, { x, y: depth });
    return x;
  }

  walk(root, 0);
  return { positions, widthUnits: Math.max(1, nextX), depth: maxDepth + 1 };
}

export function renderParseTree(root, containerEl) {
  if (!containerEl) return;
  if (!root) {
    containerEl.innerHTML = `<div class="muted">No tree to display.</div>`;
    return;
  }

  const { positions, widthUnits, depth } = layoutTree(root);
  const xSpacing = 86;
  const ySpacing = 92;
  const margin = 18;
  const viewWidth = widthUnits * xSpacing + margin * 2;
  const viewHeight = depth * ySpacing + margin * 2;

  const nodes = [];
  const edges = [];

  for (const [node, pos] of positions.entries()) {
    const x = pos.x * xSpacing + margin;
    const y = pos.y * ySpacing + margin;
    nodes.push({ node, x, y });
    for (const child of node.children ?? []) {
      const childPos = positions.get(child);
      if (!childPos) continue;
      edges.push({
        x1: x,
        y1: y,
        x2: childPos.x * xSpacing + margin,
        y2: childPos.y * ySpacing + margin,
      });
    }
  }

  const nodeWidth = 62;
  const nodeHeight = 28;

  const svg = `
    <svg viewBox="0 0 ${viewWidth} ${viewHeight}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Parse tree">
      ${edges
        .map(
          (e) =>
            `<line class="edge" x1="${e.x1}" y1="${e.y1 + nodeHeight / 2}" x2="${e.x2}" y2="${
              e.y2 - nodeHeight / 2
            }" />`,
        )
        .join("")}
      ${nodes
        .map((n) => {
          const label = escapeHtml(n.node.symbol);
          const x = n.x - nodeWidth / 2;
          const y = n.y - nodeHeight / 2;
          return `<g class="node" transform="translate(${x}, ${y})">
              <rect rx="10" ry="10" width="${nodeWidth}" height="${nodeHeight}" />
              <text x="${nodeWidth / 2}" y="${nodeHeight / 2 + 4}" text-anchor="middle">${label}</text>
            </g>`;
        })
        .join("")}
    </svg>
  `;

  containerEl.innerHTML = svg;
}

