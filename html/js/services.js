import { recommendPractice } from "./adaptive.js";
import { loadHandbook } from "./data.js";
/** Extension points. No model calls, fabricated recommendations or network sync. */
export const services = {
  knowledge: {
    ready: true, // Local draft paragraphs; not a fully reviewed knowledge base.
    async getRule(id) {
      return (
        (await loadHandbook()).paragraphs.find((rule) => rule.id === id) || null
      );
    },
    async findRules({ task, ruleIds = [] } = {}) {
      const book = await loadHandbook();
      return book.paragraphs.filter(
        (rule) => ruleIds.includes(rule.id) || rule.tasks.includes(task),
      );
    },
  },
  adaptive: {
    ready: true, // Pilot group-level selection, not the complete adaptive route.
    async recommend(input) {
      return recommendPractice(input);
    },
  },
  sync: {
    ready: false,
    async push(events) {
      return { status: "not_configured" };
    },
  },
};
