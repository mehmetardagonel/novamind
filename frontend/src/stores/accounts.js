import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { fetchEmailAccounts } from "../api/accounts";
import { Preferences } from "@capacitor/preferences";

const STALE_AFTER_MS = 60 * 1000;
const STORAGE_KEY = "accountsCache";

export const useAccountsStore = defineStore("accounts", () => {
  const accounts = ref([]);
  const loading = ref(false);
  const error = ref(null);
  const lastFetchedAt = ref(0);
  let isInitialized = false;
  let loadPromise = null;

  const hasConnectedAccounts = computed(() => accounts.value.length > 0);

  // Load cached accounts from persistent storage
  const loadFromStorage = async () => {
    // If already initialized, return immediately
    if (isInitialized) return Promise.resolve();

    // If currently loading, return the existing promise
    if (loadPromise) return loadPromise;

    // Start loading
    loadPromise = (async () => {
      try {
        const { value } = await Preferences.get({ key: STORAGE_KEY });
        if (value) {
          const cached = JSON.parse(value);
          if (cached.accounts && cached.fetchedAt) {
            accounts.value = cached.accounts;
            lastFetchedAt.value = cached.fetchedAt;
          }
        }
      } catch (err) {
        console.warn("[accounts] Failed to load from storage:", err);
      }

      isInitialized = true;
      loadPromise = null;
    })();

    return loadPromise;
  };

  // Save accounts to persistent storage
  const saveToStorage = async () => {
    try {
      await Preferences.set({
        key: STORAGE_KEY,
        value: JSON.stringify({
          accounts: accounts.value,
          fetchedAt: lastFetchedAt.value,
        }),
      });
    } catch (err) {
      console.warn("[accounts] Failed to save to storage:", err);
    }
  };

  const fetchAccounts = async ({ force = false } = {}) => {
    // Load from storage first
    await loadFromStorage();

    if (loading.value) return accounts.value;

    // Check if cache is fresh
    if (!force && accounts.value.length > 0) {
      if (Date.now() - lastFetchedAt.value < STALE_AFTER_MS) {
        return accounts.value;
      }
    }

    loading.value = true;
    error.value = null;
    try {
      const data = await fetchEmailAccounts();
      accounts.value = Array.isArray(data) ? data : [];
      lastFetchedAt.value = Date.now();

      // Save to persistent storage
      await saveToStorage();

      return accounts.value;
    } catch (err) {
      console.error("Failed to load email accounts:", err);
      error.value = err?.message || "Failed to load accounts.";
      accounts.value = accounts.value || [];
      return accounts.value;
    } finally {
      loading.value = false;
    }
  };

  // Initialize on store creation
  loadFromStorage();

  return {
    accounts,
    loading,
    error,
    lastFetchedAt,
    hasConnectedAccounts,
    fetchAccounts,
    loadFromStorage,
  };
});
