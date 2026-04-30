export function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function setUnionInto(targetSet, sourceIterable) {
  let changed = false;
  for (const value of sourceIterable) {
    if (!targetSet.has(value)) {
      targetSet.add(value);
      changed = true;
    }
  }
  return changed;
}

export function setEquals(a, b) {
  if (a.size !== b.size) return false;
  for (const value of a) {
    if (!b.has(value)) return false;
  }
  return true;
}

export function sortedArray(iterable) {
  return [...iterable].sort((left, right) => {
    if (left === right) return 0;
    return left < right ? -1 : 1;
  });
}

export function uniqueName(base, usedNames) {
  if (!usedNames.has(base)) return base;
  let candidate = base;
  while (usedNames.has(candidate)) {
    candidate = `${candidate}'`;
  }
  return candidate;
}

