import { defineStore } from "pinia";
import { ref } from "vue";

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

export const useEmailCacheStore = defineStore("emailCache", () => {
  const folders = ref({});

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

  return {
    folders,
    ensureFolder,
    getFolder: ensureFolder,
    isFresh,
    setError,
    fetchFolder,
  };
});
