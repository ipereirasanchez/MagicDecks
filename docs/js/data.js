// Fetch + in-memory cache of the generated JSON files.

export class DataError extends Error {
  constructor(message, { url, status } = {}) {
    super(message);
    this.name = "DataError";
    this.url = url;
    this.status = status;
  }
}

const cache = new Map();

async function getJson(url) {
  if (cache.has(url)) return cache.get(url);
  let res;
  try {
    res = await fetch(url, { cache: "no-cache" });
  } catch (err) {
    throw new DataError(err.message || "network error", { url, status: 0 });
  }
  if (!res.ok) throw new DataError(`HTTP ${res.status}`, { url, status: res.status });
  let data;
  try {
    data = await res.json();
  } catch (err) {
    throw new DataError(`invalid JSON: ${err.message}`, { url, status: res.status });
  }
  cache.set(url, data);
  return data;
}

/** GET data/index.json (cached after the first success). */
export function loadIndex() {
  return getJson("data/index.json");
}

/** GET data/decks/<slug>.json (cached). A 404 surfaces as DataError with status 404. */
export function loadDeck(slug) {
  return getJson(`data/decks/${encodeURIComponent(slug)}.json`);
}

export function clearCache() {
  cache.clear();
}
