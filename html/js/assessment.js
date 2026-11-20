/** Current response policies; independent of DOM, history and learning status. */
function text(value) {
  return String(value)
    .normalize("NFC")
    .trim()
    .toLowerCase()
    .replaceAll("ё", "е");
}
function matchesNumbers(input, numbers) {
  if (/[\s,;]/u.test(input)) {
    const parts = input.split(/[\s,;]+/u);
    return parts.length === numbers.length && [...numbers].sort().join(",") === parts.sort().join(",");
  }
  if (!numbers.length) return input === "";
  return numbers.some((n, i) => input.startsWith(n) &&
    matchesNumbers(input.slice(n.length), numbers.filter((_, index) => i !== index)));
}

export function checkResponse(type, actual, expected, sentenceNumbers = []) {
  if (Array.isArray(expected))
    return expected.some((answer) => checkResponse(type, actual, answer, sentenceNumbers));
  if (type === "multiple_choice" || type === "position_set") {
    const canonical = (value) =>
      text(value)
        .replace(/[\s,;]/g, "")
        .split("")
        .sort()
        .join("");
    return canonical(actual) === canonical(expected);
  }
  const input = text(actual), key = text(expected);
  if (type === "sentence_numbers" && sentenceNumbers.length && key === sentenceNumbers.join(""))
    return matchesNumbers(input, sentenceNumbers);
  if (type === "short_text" && input === key.replace(/\s+/gu, "")) return true;
  return input === key;
}
