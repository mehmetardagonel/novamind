import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { fetchEmails, fetchUnifiedEmails } from "../api/emails";

const TTL_MS = 2 * 60 * 1000;

const createFolderState = () => ({
  items: [],
  next_cursor: null,
  fetched_at: 0,
  is_loading: false,
  error: null,
  request_id: 0,
});

const normalizeResponse = (data) => {
  if (Array.isArray(data)) {
    return { items: data, next_cursor: null };
  }
  if (data && Array.isArray(data.items)) {
    return { items: data.items, next_cursor: data.next_cursor ?? null };
  }
  if (data && Array.isArray(data.emails)) {
    return { items: data.emails, next_cursor: data.next_cursor ?? null };
  }
  return { items: [], next_cursor: data?.next_cursor ?? null };
};

export const useEmailsStore = defineStore("emails", () => {
  const folders = ref({});
  const bootStatus = ref("idle");
  const bootTotal = ref(0);
  const bootDone = ref(0);
  const bootSucceeded = ref(0);
  const bootFailed = ref(0);
  const bootErrorMessage = ref(null);
  const lastBootAt = ref(null);

  const bootPercent = computed(() => {
    if (!bootTotal.value) return 0;
    return Math.round((bootDone.value / bootTotal.value) * 100);
  });

  const bootText = computed(() => `${bootDone.value} / ${bootTotal.value}`);

  const ensureFolder = (key) => {
    if (!folders.value[key]) {
      folders.value[key] = createFolderState();
    }
    return folders.value[key];
  };

  const isFresh = (key) => {
    const folder = ensureFolder(key);
    if (!folder.fetched_at) return false;
    return Date.now() - folder.fetched_at < TTL_MS;
  };

  const setError = (key, message) => {
    const folder = ensureFolder(key);
    folder.error = message || null;
  };

  const fetchFolder = async (
    key,
    fetcher,
    { force = false, append = false, cursor = null, onError, transformItems } = {}
  ) => {
    const folder = ensureFolder(key);
    if (folder.is_loading) {
      return { status: "loading", folder };
    }

    if (!append && !force && folder.items.length > 0 && isFresh(key)) {
      return { status: "fresh", folder };
    }

    folder.is_loading = true;
    folder.error = null;
    const requestId = ++folder.request_id;

    try {
      const data = await fetcher(cursor);
      if (requestId !== folder.request_id) {
        return { status: "stale", folder };
      }

      let { items, next_cursor } = normalizeResponse(data);
      if (transformItems) {
        items = transformItems(items);
      }

      folder.items = append ? folder.items.concat(items) : items;
      folder.next_cursor = next_cursor ?? null;
      folder.fetched_at = Date.now();

      return { status: "ok", folder };
    } catch (error) {
      if (requestId !== folder.request_id) {
        return { status: "stale", folder };
      }

      if (onError) {
        const handled = onError(error);
        if (handled?.skipStoreError) {
          return { status: "error", folder, error };
        }
        if (handled?.message) {
          folder.error = handled.message;
          return { status: "error", folder, error };
        }
      }

      folder.error = error?.message || "Failed to load emails.";
      return { status: "error", folder, error };
    } finally {
      if (requestId === folder.request_id) {
        folder.is_loading = false;
      }
    }
  };

  const decorateEmails = (list) => {
    return (list || []).map((email) => {
      const labels = email.label_ids || [];
      const isStarred = Array.isArray(labels) && labels.includes("STARRED");
      const isUnread = Array.isArray(labels) && labels.includes("UNREAD");

      return {
        ...email,
        isStarred,
        isUnread,
      };
    });
  };

  const prefetchMailboxAfterLogin = async ({
    force = false,
    concurrency = 3,
    maxPerAccount = 25,
    staleAfterMs = 60 * 1000,
  } = {}) => {
    if (bootStatus.value === "booting") return;
    if (!force && lastBootAt.value && Date.now() - lastBootAt.value < staleAfterMs) {
      if (bootStatus.value === "ready") return;
    }

    bootStatus.value = "booting";
    bootErrorMessage.value = null;
    bootDone.value = 0;
    bootSucceeded.value = 0;
    bootFailed.value = 0;

    // CRITICAL: Only prefetch inbox on first load, others can be lazy loaded
    const folderKeys = [
      "inbox",
      // Defer other folders - they'll be cached when user visits them
    ];

    bootTotal.value = folderKeys.length;

    let cursor = 0;
    const runNext = async () => {
      if (cursor >= folderKeys.length) return;
      const key = folderKeys[cursor++];
      const folder = ensureFolder(key);
      const shouldFetch =
        force || folder.items.length === 0 || !isFresh(key);

      if (!shouldFetch) {
        bootSucceeded.value += 1;
        bootDone.value += 1;
        return runNext();
      }

      const fetcher =
        key === "inbox"
          ? () => fetchUnifiedEmails(null, null, {}, maxPerAccount)
          : () => fetchEmails(key);

      try {
        const result = await fetchFolder(key, fetcher, {
          force: true,
          append: false,
          onError: (error) => {
            console.error("Mailbox prefetch error:", error);
            return { message: "Failed to prefetch emails." };
          },
          transformItems: decorateEmails,
        });

        if (result.status === "ok" || result.status === "fresh" || result.folder.items.length > 0) {
          bootSucceeded.value += 1;
        } else {
          bootFailed.value += 1;
        }
      } catch (error) {
        console.error("Mailbox prefetch error:", error);
        bootFailed.value += 1;
      } finally {
        bootDone.value += 1;
        return runNext();
      }
    };

    const workers = [];
    const workerCount = Math.min(concurrency, folderKeys.length);
    for (let i = 0; i < workerCount; i += 1) {
      workers.push(runNext());
    }

    await Promise.all(workers);

    lastBootAt.value = Date.now();
    if (bootSucceeded.value > 0) {
      bootStatus.value = "ready";
    } else {
      bootStatus.value = "error";
      bootErrorMessage.value = "We couldn't load your mailbox. Please try again.";
    }
  };

  return {
    folders,
    ensureFolder,
    getFolder: ensureFolder,
    isFresh,
    setError,
    fetchFolder,
    bootStatus,
    bootTotal,
    bootDone,
    bootSucceeded,
    bootFailed,
    bootErrorMessage,
    lastBootAt,
    bootPercent,
    bootText,
    prefetchMailboxAfterLogin,
  };
});
