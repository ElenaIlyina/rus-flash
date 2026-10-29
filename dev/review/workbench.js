import {
  loadReviewDebug,
  debugPage,
  debugPanel,
  toggleAccepted,
} from "./review-debug.js";
const queue = document.querySelector("#queue");
const details = document.querySelector("#details");
const frame = document.querySelector("#preview");
let entries = [],
  filter = "pending";
function render() {
  const [path, query] = location.hash.slice(1).split("?");
  if (path === "debug")
    filter = new URLSearchParams(query).get("filter") || "pending";
  queue.innerHTML = debugPage(entries, filter);
  const id = /^card\/([0-9A-F]{6})$/.exec(path)?.[1];
  const entry = entries.find((item) => item.id === id);
  details.innerHTML = entry
    ? debugPanel(entry)
    : "<p>Выберите карточку из очереди.</p>";
  frame.hidden = !id;
  if (id && frame.contentWindow.location.hash !== `#card/${id}`)
    frame.src = `../../html/index.html#card/${id}`;
}
frame.addEventListener("load", () => {
  frame.contentWindow.addEventListener("hashchange", () => {
    if (/^#card\/[0-9A-F]{6}$/.test(frame.contentWindow.location.hash))
      location.hash = frame.contentWindow.location.hash;
  });
});
document.addEventListener("click", (event) => {
  const button = event.target.closest('[data-action="debug-accept"]');
  if (!button) return;
  const entry = entries.find((item) => item.id === button.dataset.card);
  if (entry) {
    toggleAccepted(entry);
    render();
  }
});
window.addEventListener("hashchange", render);
try {
  entries = await loadReviewDebug();
  render();
} catch (error) {
  details.textContent = `${error.message}. Запустите python3 dev/scripts/build_review_data.py.`;
}
