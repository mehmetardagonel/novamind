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
      console.warn("[accounts.js] Supabase getUser error:", error);
      return "default-user";
    }

    const userId = data?.user?.id;
    return userId || "default-user";
  } catch (e) {
    console.warn("[accounts.js] Supabase getUser threw:", e);
    return "default-user";
  }
}

/**
 * Fetch all Gmail accounts for the current user
 */
export const fetchGmailAccounts = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const response = await apiClient.get("/gmail/accounts", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return response.data;
};

/**
 * Initiate OAuth flow to connect a new Gmail account
 * Returns auth URL to redirect user to
 */
export const connectGmailAccount = async (userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const response = await apiClient.get("/gmail/auth/connect", {
    headers: { "X-User-Id": resolvedUserId },
  });
  return response.data.auth_url;
};

/**
 * Set an account as primary
 */
export const setPrimaryAccount = async (accountId, userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const response = await apiClient.post(
    `/gmail/accounts/${accountId}/set-primary`,
    {},
    {
      headers: { "X-User-Id": resolvedUserId },
    }
  );
  return response.data;
};

/**
 * Delete/disconnect a Gmail account
 */
export const deleteGmailAccount = async (accountId, userId) => {
  const resolvedUserId = await resolveUserId(userId);
  const response = await apiClient.delete(`/gmail/accounts/${accountId}`, {
    headers: { "X-User-Id": resolvedUserId },
  });
  return response.data;
};
