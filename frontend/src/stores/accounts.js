import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { fetchEmailAccounts } from "../api/accounts";

const STALE_AFTER_MS = 60 * 1000;

export const useAccountsStore = defineStore("accounts", () => {
  const accounts = ref([]);
  const loading = ref(false);
  const error = ref(null);
  const lastFetchedAt = ref(0);

  const hasConnectedAccounts = computed(() => accounts.value.length > 0);

  const fetchAccounts = async ({ force = false } = {}) => {
    if (loading.value) return accounts.value;
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

  return {
    accounts,
    loading,
    error,
    lastFetchedAt,
    hasConnectedAccounts,
    fetchAccounts,
  };
});
