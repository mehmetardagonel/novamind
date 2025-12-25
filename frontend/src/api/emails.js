// src/api/emails.js
import apiClient from "./client";
import { supabase } from "@/database/supabaseClient";

/**
 * ============================================================
 *  INTERNAL: RESOLVE USER ID (from Supabase or explicit param)
 * ============================================================
 */

async function resolveUserId(explicitUserId) {
  if (explicitUserId) return explicitUserId;

  try {
    const { data, error } = await supabase.auth.getUser();

    if (error) {
      console.warn("[emails.js] Supabase getUser error:", error);
      return "default-user";
    }

    const userId = data?.user?.id;
    return userId || "default-user";
  } catch (e) {
    console.warn("[emails.js] Supabase getUser threw:", e);
    return "default-user";
  }
}

/**
 * ============================================================
 *  MAIN UNIVERSAL FETCH FUNCTION – Routes folder → endpoint
 * ============================================================
 */

export const fetchEmails = async (folder = "inbox", userId, filters = {}) => {
  if (folder.startsWith("label:")) {
    const labelId = folder.split(":")[1];

    // call custom endpoint
    const resolvedUserId = await resolveUserId(userId);

    const params = new URLSearchParams();

    if (filters.sender) params.append("sender", filters.sender);
    if (filters.subject_contains)
      params.append("subject_contains", filters.subject_contains);
    if (filters.unread !== undefined)
      params.append("unread", String(filters.unread));

    const res = await apiClient.get(
      `/emails/by-label/${encodeURIComponent(labelId)}?${params.toString()}`,
      {
        headers: { "X-User-Id": resolvedUserId },
      }
    );

    return res.data;
  }
  let endpoint = "/read-email";
  let useFilters = true;

  // Folder routing
  switch (folder) {
    case "inbox":
      endpoint = "/read-email";
      break;

    case "starred":
    case "favorites":
      endpoint = "/emails/favorites";
      useFilters = false;
      break;

    case "sent":
      endpoint = "/emails/sent";
      useFilters = false;
      break;

    case "drafts":
      endpoint = "/emails/drafts";
      useFilters = false;
      break;

    case "important":
      endpoint = "/emails/important";
      useFilters = false;
      break;

    case "spam":
      endpoint = "/emails/spam";
      useFilters = false;
      break;

    case "trash":
      endpoint = "/emails/trash";
      useFilters = false;
      break;

    default:
      endpoint = "/read-email";
      break;
  }

  // If folder supports searching (Inbox), apply filters
  if (useFilters) {
    const params = new URLSearchParams();

    if (filters.sender) params.append("sender", filters.sender);
    if (filters.subject_contains)
      params.append("subject_contains", filters.subject_contains);

    // Allow both true and false for unread
    if (filters.unread !== undefined)
      params.append("unread", String(filters.unread));

    if (filters.labels && filters.labels.length > 0) {
      filters.labels.forEach((label) => params.append("labels", label));
    }

    if (filters.newer_than_days != null) {
      params.append("newer_than_days", String(filters.newer_than_days));
    }
    if (filters.since) params.append("since", filters.since);
    if (filters.until) params.append("until", filters.until);

    const query = params.toString();
    if (query) {
      endpoint += `?${query}`;
    }
  }

  const resolvedUserId = await resolveUserId(userId);

  const response = await apiClient.get(endpoint, {
    headers: { "X-User-Id": resolvedUserId },
  });

  return response.data;
};

/**
 * ============================================================
 *   DIRECT ENDPOINT WRAPPERS
 * ============================================================
 */

export const getDraftEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/drafts", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const getSentEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/sent", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const getStarredEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/favorites", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const getImportantEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/important", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const getSpamEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/spam", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const getTrashEmails = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.get("/emails/trash", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const fetchUnifiedEmails = async (userId, accountId = null, filters = {}, maxPerAccount = 25) => {
  const resolvedUserId = await resolveUserId(userId);

  const params = new URLSearchParams();

  // Add account_id if filtering by specific account
  if (accountId) params.append("account_id", accountId);
  if (maxPerAccount) params.append("max_per_account", String(maxPerAccount));
  if (filters.sender) params.append("sender", filters.sender);
  if (filters.subject_contains)
    params.append("subject_contains", filters.subject_contains);
  if (filters.unread !== undefined)
    params.append("unread", String(filters.unread));
  if (filters.labels && filters.labels.length > 0) {
    filters.labels.forEach((label) => params.append("labels", label));
  }
  if (filters.newer_than_days != null) {
    params.append("newer_than_days", String(filters.newer_than_days));
  }
  if (filters.since) params.append("since", filters.since);
  if (filters.until) params.append("until", filters.until);

  const query = params.toString();
  const endpoint = query ? `/read-email/unified?${query}` : "/read-email/unified";

  const res = await apiClient.get(endpoint, {
    headers: { "X-User-Id": resolvedUserId },
  });

  return res.data;
};

export const logoutGmail = async () => {
  // No X-User-Id needed, backend /logout is global for now
  const res = await apiClient.post("/logout");
  return res.data;
};

/**
 * ============================================================
 *   MUTATION ENDPOINTS
 * ============================================================
 */

export const deleteEmail = async (messageId, userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.delete(`/emails/${messageId}`, {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
};

export const restoreEmail = async (messageId, userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.post(
    `/emails/${messageId}/restore`,
    {},
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );
  return res.data;
};

export const setEmailStar = async (messageId, starred, userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const res = await apiClient.post(
    `/emails/${messageId}/star`,
    starred, // ✅ send true/false directly
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );
  return res.data;
};

/**
 * ============================================================
 *   SEARCH PRESETS (Inbox Only)
 * ============================================================
 */

export const getTodayEmails = (userId) =>
  fetchEmails("inbox", userId, { newer_than_days: 1 });

export const getUnreadEmails = (userId) =>
  fetchEmails("inbox", userId, { unread: true });

export const getEmailsByLabel = async (labelId, userId) => {
  const resolvedUserId = await resolveUserId(userId);

  const res = await apiClient.get(
    `/emails/by-label/${encodeURIComponent(labelId)}`,
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );

  return res.data;
};

export const searchBySender = (sender, userId) =>
  fetchEmails("inbox", userId, { sender });

export const searchBySubject = (subject, userId) =>
  fetchEmails("inbox", userId, { subject_contains: subject });

export const searchEmails = async (query, userId, options = {}) => {
  const resolvedUserId = await resolveUserId(userId);

  const params = new URLSearchParams();
  params.append("query", query);

  if (options.provider) params.append("provider", options.provider);
  if (options.accountId) params.append("account_id", options.accountId);
  if (options.maxResults) params.append("max_results", String(options.maxResults));

  const endpoint = `/search-emails?${params.toString()}`;

  const res = await apiClient.get(endpoint, {
    headers: { "X-User-Id": resolvedUserId },
  });

  return res.data;
};

// ============================================================
//   LABEL MANAGEMENT
// ============================================================
export async function fetchLabels(userId) {
  const resolvedUserId = await resolveUserId(userId);

  const res = await apiClient.get("/labels", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return res.data;
}

export async function createLabel(name, userId) {
  const resolvedUserId = await resolveUserId(userId);

  const res = await apiClient.post(
    "/labels",
    { name },
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );
  return res.data;
}

export async function deleteLabel(id, userId) {
  const resolvedUserId = await resolveUserId(userId);

  await apiClient.delete(`/labels/${encodeURIComponent(id)}`, {
    headers: { "X-User-Id": resolvedUserId },
  });
}

export const updateEmailLabels = async (
  messageId,
  { addLabelIds = [], removeLabelIds = [] } = {},
  userId
) => {
  const resolvedUserId = await resolveUserId(userId);

  const res = await apiClient.post(
    `/emails/${encodeURIComponent(messageId)}/labels`,
    {
      add_label_ids: addLabelIds,
      remove_label_ids: removeLabelIds,
    },
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );

  return res.data;
};

export default {
  fetchEmails,
  getDraftEmails,
  getSentEmails,
  getStarredEmails,
  getImportantEmails,
  getSpamEmails,
  getTrashEmails,
  fetchUnifiedEmails,
  deleteEmail,
  restoreEmail,
  setEmailStar,
  getTodayEmails,
  getUnreadEmails,
  getEmailsByLabel,
  searchBySender,
  searchBySubject,
  searchEmails,
  logoutGmail,
  fetchLabels,
  createLabel,
  deleteLabel,
  updateEmailLabels,
};
