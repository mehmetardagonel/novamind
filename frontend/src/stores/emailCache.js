import { defineStore } from "pinia";
import { reactive } from "vue";
import { Preferences } from "@capacitor/preferences";

const STORAGE_KEY = "emailCache";

export const useEmailCacheStore = defineStore("emailCache", () => {
  const entries = reactive({});
  const inFlight = new Map();
  let isInitialized = false;

  // Load cached data from persistent storage
  async function loadFromStorage() {
    if (isInitialized) return;

    try {
      const { value } = await Preferences.get({ key: STORAGE_KEY });
      if (value) {
        const stored = JSON.parse(value);
        Object.assign(entries, stored);
      }
    } catch (error) {
      console.warn("[emailCache] Failed to load from storage:", error);
    }

    isInitialized = true;
  }

  // Save current cache to persistent storage
  async function saveToStorage() {
    try {
      await Preferences.set({
        key: STORAGE_KEY,
        value: JSON.stringify(entries),
      });
    } catch (error) {
      console.warn("[emailCache] Failed to save to storage:", error);
    }
  }

  function getEntry(key) {
    return entries[key] ?? null;
  }

  async function setEntry(key, value) {
    entries[key] = { value, fetchedAt: Date.now() };
    await saveToStorage();
  }

  async function updateValue(key, value) {
    const entry = getEntry(key);
    if (!entry) {
      await setEntry(key, value);
      return;
    }
    entry.value = value;
    await saveToStorage();
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
      await setEntry(key, value);
      return value;
    })().finally(() => {
      inFlight.delete(key);
    });

    inFlight.set(key, promise);
    return promise;
  }

  async function invalidate(key) {
    delete entries[key];
    inFlight.delete(key);
    await saveToStorage();
  }

  async function invalidateAll() {
    for (const key of Object.keys(entries)) {
      delete entries[key];
    }
    inFlight.clear();
    await saveToStorage();
  }

  // Initialize on store creation
  loadFromStorage();

  return {
    entries,
    getEntry,
    setEntry,
    updateValue,
    isFresh,
    fetchOnce,
    invalidate,
    invalidateAll,
    loadFromStorage,
  };
});
