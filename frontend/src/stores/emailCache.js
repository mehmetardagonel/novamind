import { defineStore } from "pinia";
import { reactive } from "vue";

export const useEmailCacheStore = defineStore("emailCache", () => {
  const entries = reactive({});
  const inFlight = new Map();

  function getEntry(key) {
    return entries[key] ?? null;
  }

  function setEntry(key, value) {
    entries[key] = { value, fetchedAt: Date.now() };
  }

  function updateValue(key, value) {
    const entry = getEntry(key);
    if (!entry) {
      setEntry(key, value);
      return;
    }
    entry.value = value;
  }

  function isFresh(key, staleTimeMs) {
    const entry = getEntry(key);
    if (!entry) return false;
    return Date.now() - entry.fetchedAt < staleTimeMs;
  }

  async function fetchOnce(key, fetcher) {
    if (inFlight.has(key)) return inFlight.get(key);

    const promise = (async () => {
      const value = await fetcher();
      setEntry(key, value);
      return value;
    })().finally(() => {
      inFlight.delete(key);
    });

    inFlight.set(key, promise);
    return promise;
  }

  function invalidate(key) {
    delete entries[key];
    inFlight.delete(key);
  }

  function invalidateAll() {
    for (const key of Object.keys(entries)) {
      delete entries[key];
    }
    inFlight.clear();
  }

  return {
    entries,
    getEntry,
    setEntry,
    updateValue,
    isFresh,
    fetchOnce,
    invalidate,
    invalidateAll,
  };
});

