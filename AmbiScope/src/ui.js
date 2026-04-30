import { ENDMARKER, EPSILON } from "./constants.js";
import { renderParseTree } from "./render_tree.js";
import { escapeHtml, sortedArray } from "./util.js";

const EXAMPLE = {
  grammar: [
    "E -> T E'",
    "E' -> + T E' | ε",
    "T -> F T'",
    "T' -> * F T' | ε",
    "F -> ( E ) | id",
  ].join("\n"),
  input: "id + id * id",
};

const els = {
  grammarInput: document.getElementById("grammarInput"),
  startSymbolInput: document.getElementById("startSymbolInput"),
  parserSelect: document.getElementById("parserSelect"),
  inputString: document.getElementById("inputString"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  runBtn: document.getElementById("runBtn"),
  resetBtn: document.getElementById("resetBtn"),
  prevStepBtn: document.getElementById("prevStepBtn"),
  nextStepBtn: document.getElementById("nextStepBtn"),
  playPauseBtn: document.getElementById("playPauseBtn"),
  loadExampleBtn: document.getElementById("loadExampleBtn"),
  statusBox: document.getElementById("statusBox"),
  grammarSummary: document.getElementById("grammarSummary"),
  warningsBox: document.getElementById("warningsBox"),
  setsBox: document.getElementById("setsBox"),
  tableBox: document.getElementById("tableBox"),
  traceBox: document.getElementById("traceBox"),
  treeBox: document.getElementById("treeBox"),
  stateSelect: document.getElementById("stateSelect"),
  stateItems: document.getElementById("stateItems"),
};

const app = {
  analysis: null,
  simulation: null,
  stepIndex: 0,
  playTimer: null,
};

async function apiPost(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data?.ok) {
    throw new Error(data?.error ?? `Request failed (${res.status})`);
  }
  return data;
}

function setStatus(html, variant = "info") {
  const prefix =
    variant === "ok"
      ? `<span class="badge ok">OK</span>`
      : variant === "warn"
        ? `<span class="badge warn">WARN</span>`
        : variant === "danger"
          ? `<span class="badge danger">ERROR</span>`
          : `<span class="badge">INFO</span>`;
  els.statusBox.innerHTML = `${prefix} ${html}`;
}

function fmtSet(items) {
  const values = Array.isArray(items) ? items : [];
  const sorted = sortedArray(values);
  return `{ ${sorted.join(", ")} }`;
}

function warningBadge(level) {
  if (level === "ok") return `<span class="badge ok">OK</span>`;
  if (level === "warn") return `<span class="badge warn">WARN</span>`;
  if (level === "danger") return `<span class="badge danger">ERROR</span>`;
  return `<span class="badge">INFO</span>`;
}

function formatWarning(w) {
  const message = escapeHtml(w?.message ?? "");
  const details = w?.details;
  if (Array.isArray(details) && details.length) {
    return `${warningBadge(w.level)} ${message}: <code>${escapeHtml(details.join(", "))}</code>`;
  }
  return `${warningBadge(w.level)} ${message}`;
}

function fmtProd(grammar, prodId) {
  const prod = grammar?.productions?.[prodId];
  if (!prod) return "";
  const rhs = prod.rhs?.length ? prod.rhs.join(" ") : EPSILON;
  return `${prod.lhs} → ${rhs}`;
}

function renderGrammarSummary(grammar) {
  const nts = sortedArray(grammar?.nonterminals ?? []);
  const ts = sortedArray(grammar?.terminals ?? []);
  const prods = (grammar?.productions ?? [])
    .map((p) => `${escapeHtml(p.lhs)} → ${escapeHtml(p.rhs?.length ? p.rhs.join(" ") : EPSILON)}`)
    .join("<br />");

  els.grammarSummary.innerHTML = `
    <div><span class="badge">Start</span> <strong>${escapeHtml(grammar.startSymbol)}</strong></div>
    <div style="margin-top: 8px"><span class="badge">Nonterminals</span> ${escapeHtml(nts.join(", "))}</div>
    <div style="margin-top: 6px"><span class="badge">Terminals</span> ${escapeHtml(ts.join(", "))}</div>
    <div style="margin-top: 10px"><span class="badge">Productions</span></div>
    <div style="margin-top: 6px; line-height: 1.55">${prods}</div>
  `;
}

function renderFirstFollow(grammar, firstSets, followSets) {
  const nts = sortedArray(grammar?.nonterminals ?? []);
  const rows = nts
    .map((nt) => {
      const first = firstSets?.[nt] ?? [];
      const follow = followSets?.[nt] ?? [];
      return `<tr><td><code>${escapeHtml(nt)}</code></td><td>${escapeHtml(
        fmtSet(first),
      )}</td><td>${escapeHtml(fmtSet(follow))}</td></tr>`;
    })
    .join("");

  els.setsBox.innerHTML = `
    <table>
      <thead><tr><th>Nonterminal</th><th>FIRST</th><th>FOLLOW</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderWarnings(warnings) {
  const list = Array.isArray(warnings) ? warnings : [];
  if (!list.length) {
    els.warningsBox.innerHTML = `<span class="badge ok">No conflicts detected</span>`;
    return;
  }
  els.warningsBox.innerHTML = list.map((w) => `<div style="margin: 6px 0">${formatWarning(w)}</div>`).join("");
}

function renderLL1Table(grammar, ll1) {
  const terminals = sortedArray([...(grammar?.terminals ?? []), ENDMARKER]);
  const nonterminals = sortedArray(grammar?.nonterminals ?? []);
  const conflictKeys = new Set(
    (ll1?.conflicts ?? []).map((c) => `${c.nonterminal}|||${c.terminal}`),
  );

  const head = `<tr><th>Nonterminal</th>${terminals
    .map((t) => `<th>${escapeHtml(t)}</th>`)
    .join("")}</tr>`;

  const rows = nonterminals
    .map((nt) => {
      const row = ll1?.table?.[nt] ?? {};
      const cells = terminals
        .map((t) => {
          const prodId = row?.[t];
          const conflictClass = conflictKeys.has(`${nt}|||${t}`) ? "conflict" : "";
          if (prodId === undefined) return `<td class="${conflictClass}"></td>`;
          return `<td class="${conflictClass}"><code>${escapeHtml(fmtProd(grammar, prodId))}</code></td>`;
        })
        .join("");
      return `<tr><td><code>${escapeHtml(nt)}</code></td>${cells}</tr>`;
    })
    .join("");

  els.tableBox.innerHTML = `<table><thead>${head}</thead><tbody>${rows}</tbody></table>`;
}

function fmtActionCell(actions) {
  if (!Array.isArray(actions)) return "";
  return actions
    .map((a) => {
      if (a.type === "shift") return `s${a.to}`;
      if (a.type === "reduce") return `r${a.production}`;
      if (a.type === "accept") return "acc";
      return "?";
    })
    .join(" / ");
}

function renderLRTable(lr) {
  const terminals = sortedArray([...(lr?.grammar?.terminals ?? []), ENDMARKER]);
  const nonterminals = sortedArray(lr?.grammar?.nonterminals ?? []);

  const head = `<tr><th rowspan="2">State</th><th colspan="${terminals.length}">ACTION</th><th colspan="${nonterminals.length}">GOTO</th></tr>
    <tr>${terminals.map((t) => `<th>${escapeHtml(t)}</th>`).join("")}${nonterminals
      .map((nt) => `<th>${escapeHtml(nt)}</th>`)
      .join("")}</tr>`;

  const rowCount = lr?.states?.length ?? 0;

  const rows = Array.from({ length: rowCount }, (_, state) => {
    const actionRow = lr?.actionTable?.[String(state)] ?? {};
    const gotoRow = lr?.gotoTable?.[String(state)] ?? {};

    const actionCells = terminals
      .map((t) => {
        const cell = actionRow?.[t] ?? [];
        const conflictClass = Array.isArray(cell) && cell.length > 1 ? "conflict" : "";
        const text = fmtActionCell(cell);
        if (!text) return "<td></td>";
        return `<td class="${conflictClass}"><code>${escapeHtml(text)}</code></td>`;
      })
      .join("");

    const gotoCells = nonterminals
      .map((nt) => {
        const to = gotoRow?.[nt];
        return to === undefined ? "<td></td>" : `<td><code>${escapeHtml(String(to))}</code></td>`;
      })
      .join("");

    return `<tr><td><code>${state}</code></td>${actionCells}${gotoCells}</tr>`;
  }).join("");

  els.tableBox.innerHTML = `<table><thead>${head}</thead><tbody>${rows}</tbody></table>`;
}

function renderTrace(sim) {
  if (!sim?.steps?.length) {
    els.traceBox.innerHTML = `<div class="muted">No simulation yet.</div>`;
    return;
  }

  const rows = sim.steps
    .map((s, idx) => {
      const isActive = idx === app.stepIndex;
      let stackText = "";
      if (Array.isArray(s.stack) && s.stack.length) {
        if (typeof s.stack[0] === "string") {
          stackText = s.stack.join(" ");
        } else {
          stackText = s.stack
            .map((entry, entryIdx) =>
              entryIdx === 0 ? String(entry.state) : `${entry.symbol ?? ""} ${entry.state}`,
            )
            .join(" ")
            .trim();
        }
      }

      const inputHtml = (s.input ?? [])
        .map((tok, i) => `<span class="tok ${i === s.pointer ? "active" : ""}">${escapeHtml(tok)}</span>`)
        .join(" ");

      return `<tr class="${isActive ? "active" : ""}" data-step="${idx}">
        <td><code>${idx}</code></td>
        <td><code>${escapeHtml(stackText)}</code></td>
        <td>${inputHtml}</td>
        <td>${escapeHtml(s.action)}${s.note ? `<div class="muted" style="margin-top:4px">${escapeHtml(s.note)}</div>` : ""}</td>
      </tr>`;
    })
    .join("");

  els.traceBox.innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:8px">
      <div><span class="badge">Steps</span> <strong>${app.stepIndex + 1}</strong> / ${sim.steps.length}</div>
      <div class="muted">Click a row to jump</div>
    </div>
    <div style="overflow:auto;max-height:320px;border:1px solid rgba(255,255,255,0.08);border-radius:12px">
      <table>
        <thead><tr><th>#</th><th>Stack</th><th>Input</th><th>Action</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;

  els.traceBox.querySelectorAll("tr[data-step]").forEach((row) => {
    row.addEventListener("click", () => {
      const idx = Number(row.getAttribute("data-step"));
      if (!Number.isFinite(idx)) return;
      goToStep(idx);
    });
  });
}

function renderTreeForStep(sim) {
  const step = sim?.steps?.[app.stepIndex];
  const tree = step?.tree ?? sim?.tree ?? null;
  if (!tree) {
    els.treeBox.innerHTML =
      '<div class="muted">No tree to display yet. Run the parser, then click a row in <strong>Step Trace</strong> (usually the last <code>accept</code> step).</div>';
    return;
  }
  renderParseTree(tree, els.treeBox);
}

function enableSimulationControls(enabled) {
  els.resetBtn.disabled = !enabled;
  els.prevStepBtn.disabled = !enabled;
  els.nextStepBtn.disabled = !enabled;
  els.playPauseBtn.disabled = !enabled;
}

function stopPlayback() {
  if (app.playTimer) clearInterval(app.playTimer);
  app.playTimer = null;
  els.playPauseBtn.textContent = "Play";
}

function goToStep(idx) {
  if (!app.simulation?.steps?.length) return;
  const bounded = Math.max(0, Math.min(app.simulation.steps.length - 1, idx));
  app.stepIndex = bounded;
  renderTrace(app.simulation);
  renderTreeForStep(app.simulation);
}

function resetSimulation() {
  stopPlayback();
  app.simulation = null;
  app.stepIndex = 0;
  enableSimulationControls(false);
  els.runBtn.disabled = !app.analysis || !!app.analysis.hasBlockingConflicts;
  els.traceBox.innerHTML = `<div class="muted">No simulation yet.</div>`;
  renderParseTree(null, els.treeBox);
}

function formatLRStateItems(grammar, stateItems) {
  const items = Array.isArray(stateItems) ? stateItems : [];
  return items
    .map((item) => {
      const prod = grammar?.productions?.[item.production];
      if (!prod) return "";
      const rhs = [...(prod.rhs ?? [])];
      rhs.splice(item.dot ?? 0, 0, "•");
      const core = `${prod.lhs} → ${rhs.join(" ")}`;
      if (item.lookahead) return `${core} , ${item.lookahead}`;
      if (Array.isArray(item.lookaheads)) return `${core} , {${item.lookaheads.join(", ")}}`;
      return core;
    })
    .filter(Boolean)
    .join("\n");
}

function renderStateViewer(lr) {
  if (!lr?.states?.length) {
    els.stateSelect.innerHTML = "";
    els.stateSelect.disabled = true;
    els.stateItems.textContent = "No LR automaton to display.";
    els.stateSelect.onchange = null;
    return;
  }

  els.stateSelect.disabled = false;
  els.stateSelect.innerHTML = lr.states
    .map((_, idx) => `<option value="${idx}">State ${idx}</option>`)
    .join("");

  const update = () => {
    const id = Number(els.stateSelect.value);
    const state = lr.states[id];
    els.stateItems.textContent = formatLRStateItems(lr.grammar, state);
  };

  els.stateSelect.onchange = update;
  update();
}

async function analyze() {
  resetSimulation();

  try {
    setStatus("Analyzing grammar…", "info");
    const api = await apiPost("/api/analyze", {
      grammar: els.grammarInput.value,
      startSymbol: els.startSymbolInput.value,
      parserKind: els.parserSelect.value,
    });

    const analysis = api.analysis;
    app.analysis = analysis;

    renderGrammarSummary(analysis.grammar);
    renderFirstFollow(analysis.grammar, analysis.firstSets, analysis.followSets);
    renderWarnings(analysis.warnings ?? []);

    if (analysis.parserKind === "ll1") {
      renderLL1Table(analysis.grammar, analysis.ll1);
      renderStateViewer(null);
    } else {
      renderLRTable(analysis.lr);
      renderStateViewer(analysis.lr);
    }

    els.runBtn.disabled = !!analysis.hasBlockingConflicts;
    if (analysis.hasBlockingConflicts) {
      setStatus("Grammar analyzed, but conflicts were found. Fix the grammar or change the parser.", "warn");
    } else {
      setStatus("Grammar analyzed. You can run the parser now.", "ok");
    }
  } catch (err) {
    app.analysis = null;
    els.runBtn.disabled = true;
    renderWarnings([{ level: "danger", message: `Analysis failed: ${err?.message ?? String(err)}` }]);
    setStatus(`Analysis failed: <strong>${escapeHtml(err?.message ?? String(err))}</strong>`, "danger");
  }
}

async function runParser() {
  stopPlayback();

  if (!app.analysis) {
    setStatus("Analyze the grammar first.", "warn");
    return;
  }
  if (app.analysis.hasBlockingConflicts) {
    setStatus("Cannot run: parsing table conflicts exist for the selected parser.", "warn");
    return;
  }

  try {
    setStatus("Running parser…", "info");
    const api = await apiPost("/api/simulate", {
      grammar: els.grammarInput.value,
      startSymbol: els.startSymbolInput.value,
      parserKind: app.analysis.parserKind,
      input: els.inputString.value,
    });

    const sim = api.simulation;
    app.simulation = sim;
    const steps = sim.steps ?? [];
    const lastIdx = steps.length ? steps.length - 1 : 0;
    const firstTreeIdx = steps.findIndex((s) => s?.tree);
    if (sim.accepted) {
      app.stepIndex = lastIdx;
    } else if (firstTreeIdx >= 0) {
      app.stepIndex = firstTreeIdx;
    } else {
      app.stepIndex = lastIdx;
    }
    renderTrace(sim);
    renderTreeForStep(sim);
    enableSimulationControls(true);

    if (sim.accepted) setStatus("Parsing completed. Input accepted.", "ok");
    else setStatus(`Parsing stopped. ${escapeHtml(sim.error ?? "Rejected.")}`, "danger");
  } catch (err) {
    setStatus(`Run failed: <strong>${escapeHtml(err?.message ?? String(err))}</strong>`, "danger");
  }
}

function step(delta) {
  if (!app.simulation?.steps?.length) return;
  goToStep(app.stepIndex + delta);
}

function togglePlay() {
  if (!app.simulation?.steps?.length) return;
  if (app.playTimer) {
    stopPlayback();
    return;
  }

  els.playPauseBtn.textContent = "Pause";
  app.playTimer = setInterval(() => {
    if (!app.simulation?.steps?.length) {
      stopPlayback();
      return;
    }
    if (app.stepIndex >= app.simulation.steps.length - 1) {
      stopPlayback();
      return;
    }
    goToStep(app.stepIndex + 1);
  }, 650);
}

function loadExample() {
  els.grammarInput.value = EXAMPLE.grammar;
  els.inputString.value = EXAMPLE.input;
  els.startSymbolInput.value = "";
  els.parserSelect.value = "ll1";
  setStatus("Example loaded. Click Analyze Grammar.", "info");
  app.analysis = null;
  els.runBtn.disabled = true;
  resetSimulation();
  els.grammarSummary.innerHTML = "";
  els.setsBox.innerHTML = "";
  els.tableBox.innerHTML = "";
  renderWarnings([]);
  renderStateViewer(null);
}

els.analyzeBtn.addEventListener("click", analyze);
els.runBtn.addEventListener("click", runParser);
els.resetBtn.addEventListener("click", resetSimulation);
els.prevStepBtn.addEventListener("click", () => step(-1));
els.nextStepBtn.addEventListener("click", () => step(1));
els.playPauseBtn.addEventListener("click", togglePlay);
els.loadExampleBtn.addEventListener("click", loadExample);
els.parserSelect.addEventListener("change", () => {
  app.analysis = null;
  els.runBtn.disabled = true;
  resetSimulation();
  setStatus("Parser changed. Click Analyze Grammar again.", "info");
});

loadExample();
