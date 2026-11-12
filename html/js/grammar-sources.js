import { esc } from "./ui.js";

// Grammar references link to their actual source rather than the spelling book.
export function renderGrammarReferences(refs, { kind = "grammar" } = {}) {
  const summary = kind === "punctuation" ? "Пунктуация: комментарии к предложениям" : kind === "lexical" ? "Источники проверки лексики" : kind === "cohesion" ? "Источники проверки средства связи" : kind === "style" ? "Источники по стилистике" :
    kind === "morphology" ? "Источники проверки формы слова" : "Грамматические источники разбора";
  const unit = (kind === "grammar" || kind === "punctuation") ? "Предложение" : "Вариант";
  const valid = (refs || []).filter((ref) => {
    if (kind === "lexical" && ref.part === 1 && /^assets\/data\/lexical-sources\/(?:denisov-morkovkin-1983|rozental-stylistics-2001)\.pdf#page=[1-9][0-9]*$/.test(ref.url)) return true;
    try {
      const url = new URL(ref.url);
      const grammar = url.host === "gramota.ru" &&
        (url.pathname.startsWith("/biblioteka/spravochniki/") || /^\/spravka\/vopros\/[0-9]+$/.test(url.pathname) || /^\/meta\/[a-z]+(?:_[0-9]+\.h[0-9]+)?$/.test(url.pathname)) && !url.hash;
      const fipi = url.host === "doc.fipi.ru" &&
        /^\/zhurnal-fipi\/PI-[0-9]{4}-[0-9]{2}\.pdf$/.test(url.pathname) && /^#page=[1-9][0-9]*$/.test(url.hash);
      const dictionaryPdf = url.host === "gramota.ru" &&
        url.pathname === "/storage/public/normdicts/orfograficheskij_slovar.pdf" && /^#page=[1-9][0-9]*$/.test(url.hash);
      const fipiSelfPrep = ref.url === "https://doc.fipi.ru/navigator-podgotovki/navigator-ege/2023/rus_yaz_2023.pdf#page=12";
      const punctuationCommentary = ref.url === "https://profcentr.ggtu.ru/images/documents/materials_vebinar/2023/november/2811Bashkirova.pdf#page=22";
      const academic = ref.url === "https://artefact.lib.ru/languages/rus_ebooks_rg_1645-1668.shtml#p1658";
      const journalPdf = ref.url === "https://dcl.bas.bg/wp-content/uploads/2022/11/08_Letuchiy_STONTBgRu2022.pdf#page=24";
      const journal = ref.url === "https://cyberleninka.ru/article/n/ukazatelnye-mestoimeniya-v-slozhnopodchinennyh-konstruktsiyah-so-znacheniem-peredachi-vospriyatiya-ili-osmysleniya-informatsii";
      return Number.isInteger(ref.part) && ref.part >= 1 && ref.part <= 9 &&
        url.protocol === "https:" && (grammar || fipi || journal || journalPdf || dictionaryPdf || academic || punctuationCommentary || fipiSelfPrep) &&
        !url.username && !url.password && !url.search;
    } catch {
      return false;
    }
  });
  if (!valid.length) return "";
  return `<details class="explanation-sources"><summary>${summary}</summary><nav class="rule-links">${valid.map((ref) => `<a class="text-link" href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${kind === "lexical" ? "Лексика" : kind === "cohesion" ? "Средство связи" : `${unit} ${ref.part}`}: ${esc(ref.label)}</a>`).join("")}</nav></details>`;
}
