// Shorten text to a pixel width rather than a character count, so narrow
// names ("Fill indicators") keep more letters than wide ones ("MANAGEMENT").
// Used for SVG, which can't ellipsize on its own. The estimate runs during
// prerender; in the browser, `fitText` refines it with real measurements.

// Approximate advance widths in em for the UI font at semibold.
const NARROW = new Set("il.,:;'|!ijtfI1 ()[]");
const SEMI = new Set('rsJ-/"');
const WIDE = new Set('mwMW@%');

function charEm(c: string): number {
  if (NARROW.has(c)) return 0.3;
  if (SEMI.has(c)) return 0.45;
  if (WIDE.has(c)) return 0.86;
  if (c >= 'A' && c <= 'Z') return 0.68;
  if (c >= '0' && c <= '9') return 0.6;
  return 0.56;
}

/** Estimated width in px of `s` at `size` px with `tracking` em letter-spacing. */
export function textWidth(s: string, size: number, tracking = 0): number {
  let em = 0;
  for (const c of s) em += charEm(c) + tracking;
  return em * size;
}

/** `s`, or the longest prefix that fits `max` px followed by an ellipsis. */
export function fitWidth(s: string, max: number, size: number, tracking = 0): string {
  if (textWidth(s, size, tracking) <= max) return s;
  const budget = max - textWidth('…', size, tracking);
  let w = 0;
  let i = 0;
  for (const c of s) {
    w += (charEm(c) + tracking) * size;
    if (w > budget) break;
    i += c.length;
  }
  return `${s.slice(0, i).trimEnd()}…`;
}

/**
 * Svelte action for an SVG <text>: once fonts are ready, trim `text` to
 * `max` px using the browser's own measurement (the estimate above can be off
 * by a few percent either way).
 */
export function fitText(el: SVGTextElement, opts: { text: string; max: number }) {
  let current = opts;
  function apply() {
    const { text, max } = current;
    el.textContent = text;
    if (el.getComputedTextLength() <= max) return;
    let lo = 0;
    let hi = text.length;
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      el.textContent = `${text.slice(0, mid).trimEnd()}…`;
      if (el.getComputedTextLength() <= max) lo = mid;
      else hi = mid - 1;
    }
    el.textContent = `${text.slice(0, lo).trimEnd()}…`;
  }
  const ready = document.fonts?.ready ?? Promise.resolve();
  ready.then(() => apply());
  return {
    update(next: { text: string; max: number }) {
      current = next;
      apply();
    }
  };
}
