/** Extension points. No model calls, fabricated recommendations or network sync. */
export const services = {
  knowledge: {
    ready: false,
    async getRule(id) {
      return null;
    },
    async findRules({ cardId, skillIds = [] }) {
      return [];
    },
  },
  adaptive: {
    ready: false,
    async recommend({ history, skillIds = [] }) {
      return [];
    },
  },
  sync: {
    ready: false,
    async push(events) {
      return { status: "not_configured" };
    },
  },
};
