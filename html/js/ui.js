/** Shared presentation helpers: icons, numbers and safe source formatting. */
const icons = {
  study: '<path d="m9 5 11 7-11 7z"/>',
  bank: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
  progress: '<path d="M5 20V10m7 10V4m7 16v-7"/>',
  knowledge:
    '<path d="M12 6c-3-2-6-2-9-1v14c3-1 6-1 9 1 3-2 6-2 9-1V5c-3-1-6-1-9 1Zm0 0v14"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  back: '<path d="M19 12H5m5-5-5 5 5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  bookmark: '<path d="M6 4h12v17l-6-4-6 4z"/>',
  repeat: '<path d="M20 7h-9a6 6 0 1 0 5 9M16 3l4 4-4 4"/>',
  search: '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  leaf: '<path d="M5 19C1 7 9 3 21 3c0 12-4 20-16 16Zm0 0L16 8"/>',
};
export const icon = (name, cls = "") =>
  `<svg class="icon ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.knowledge}</svg>`;
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
// Retain meaningful source formatting, drop executable/unknown markup and attributes.
export function rich(value, { markdown = true } = {}) {
  const formatted = !markdown
    ? String(value || "")
    : String(value || "")
        .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[\s(«])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  const doc = new DOMParser().parseFromString(formatted, "text/html");
  const allowed = new Set([
    "B",
    "STRONG",
    "I",
    "EM",
    "U",
    "SUB",
    "SUP",
    "BR",
    "P",
  ]);
  function clean(node) {
    if (node.nodeType === Node.TEXT_NODE) return esc(node.textContent);
    if (node.nodeType !== Node.ELEMENT_NODE) return "";
    if (["SCRIPT", "STYLE", "IFRAME", "OBJECT", "SVG"].includes(node.tagName))
      return "";
    const inside = [...node.childNodes].map(clean).join("");
    if (!allowed.has(node.tagName)) return inside;
    const name = node.tagName.toLowerCase();
    return name === "br" ? "<br>" : `<${name}>${inside}</${name}>`;
  }
  return [...doc.body.childNodes].map(clean).join("").replace(/\n/g, "<br>");
}
export const plain = (s) =>
  new DOMParser().parseFromString(s || "", "text/html").body.textContent;
export const num = (n) => n.toLocaleString("ru-RU");
