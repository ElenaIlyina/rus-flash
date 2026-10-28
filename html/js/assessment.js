/** Current response policies; independent of DOM, history and learning status. */
function text(value) {
  return String(value)
    .normalize("NFC")
    .trim()
    .toLowerCase()
    .replaceAll("ё", "е");
}
export function checkResponse(type, actual, expected) {
  if (type === "multiple_choice" || type === "position_set") {
    const canonical = (value) =>
      text(value)
        .replace(/[\s,;]/g, "")
        .split("")
        .sort()
        .join("");
    return canonical(actual) === canonical(expected);
  }
  // Matching and sentence numbers preserve order: 13254 is not 52341; 26 is not 62.
  return text(actual) === text(expected);
}
