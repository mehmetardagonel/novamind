<template>
  <div class="accounts-container">
    <!-- Header with Connection Buttons and Refresh -->
    <div class="accounts-header">
      <div class="connect-buttons">
        <button
          @click="connectGmail"
          class="btn-gmail"
        >
          <svg class="provider-icon" viewBox="0 0 24 24" width="20" height="20">
            <path
              fill="currentColor"
              d="M20,18H18V9.25L12,13L6,9.25V18H4V6H5.2L12,10.25L18.8,6H20M20,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V6C22,4.89 21.1,4 20,4Z"
            />
          </svg>
          Connect to Gmail
        </button>

        <button
          @click="connectOutlook"
          class="btn-outlook"
        >
          <svg class="provider-icon" viewBox="0 0 24 24" width="20" height="20">
            <path
              fill="currentColor"
              d="M7.88,12.04Q7.88,10.73 8.61,9.85T10.5,8.96Q11.63,8.96 12.36,9.83T13.09,11.96Q13.09,13.27 12.36,14.14T10.5,15Q9.37,15 8.63,14.14T7.88,12.04M24,12V24H8V22H22V14H14.75V12H24M7.88,12.04Q7.88,13.28 8.6,14.14T10.5,15Q11.63,15 12.35,14.14T13.08,12Q13.08,10.73 12.35,9.85T10.5,8.97Q9.37,8.97 8.63,9.85T7.88,12.04M0,3V21H6V3L0,3M12,3V6H8V3H12Z"
            />
          </svg>
          Connect to Outlook
        </button>
      </div>

      <button
        @click="refreshAccounts"
        class="btn-refresh"
        :disabled="loading"
        title="Refresh accounts"
      >
        <svg class="refresh-icon" :class="{ spinning: loading }" viewBox="0 0 24 24" width="20" height="20">
          <path
            fill="currentColor"
            d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z"
          />
        </svg>
        Refresh
      </button>
    </div>

    <div v-if="loading" class="accounts-skeleton">
      <!-- show 2 skeleton cards for better performance -->
      <div class="account-card skeleton-card" v-for="i in 2" :key="i">
        <div class="account-info">
          <div class="skeleton-line w-60"></div>
          <div class="skeleton-line w-40"></div>
        </div>

        <div class="account-actions">
          <div class="skeleton-btn"></div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="accounts-list">
      <div v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-info">
          <div class="account-email">
            <span :class="['provider-badge', account.provider]">
              {{ account.provider === "gmail" ? "Gmail" : "Outlook" }}
            </span>
            {{ account.email_address }}
            <span v-if="account.is_primary" class="primary-badge">Primary</span>
          </div>
          <div class="account-name">{{ account.display_name }}</div>
          <div class="account-date">
            Connected: {{ formatDate(account.created_at) }}
          </div>
        </div>

        <div class="account-actions">
          <button
            v-if="!account.is_primary"
            @click="setPrimary(account.id)"
            class="btn-secondary"
          >
            Set as Primary
          </button>

          <button @click="deleteAccount(account.id)" class="btn-danger">
            <i class="pi pi-trash"></i>
            Disconnect
          </button>
        </div>
      </div>

      <div v-if="accounts.length === 0" class="empty-state">
        <i class="pi pi-inbox" style="font-size: 3rem; color: #ccc"></i>
        <p>No connected email accounts</p>
        <p class="empty-hint">
          Connect your Gmail or Outlook account to get started
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter } from "vue-router";
import {
  connectGmailAccount,
  connectOutlookAccount,
  setPrimaryAccount,
  deleteEmailAccount,
} from "../api/accounts";
import { useAccountsStore } from "../stores/accounts";
import { useEmailCacheStore } from "../stores/emailCache";
import { Browser } from "@capacitor/browser";
import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

const router = useRouter();
const accountsStore = useAccountsStore();
const emailCache = useEmailCacheStore();
const accounts = ref([]);
const loading = ref(false);
const error = ref(null);
let appUrlListener = null;

const loadAccounts = async () => {
  // CRITICAL: Check cache synchronously FIRST (already initialized on store creation)
  if (accountsStore.accounts.length > 0) {
    accounts.value = accountsStore.accounts;
    loading.value = false;
    // Fetch fresh data in background (will update silently)
    accountsStore.fetchAccounts({ force: false }).then(() => {
      accounts.value = accountsStore.accounts;
    }).catch(err => {
      console.warn("Background fetch failed:", err);
    });
    return;
  }

  // No cache available, show loading and fetch
  loading.value = true;
  error.value = null;
  try {
    await accountsStore.fetchAccounts({ force: true });
    accounts.value = accountsStore.accounts;
  } catch (err) {
    console.error("Failed to load accounts:", err);
    error.value = "Failed to load accounts. Please try again.";
  } finally {
    loading.value = false;
  }
};

const connectGmail = async () => {
  try {
    const authUrl = await connectGmailAccount();
    const isMobile = Capacitor.isNativePlatform();

    if (isMobile) {
      // Open OAuth in in-app browser on mobile
      await Browser.open({
        url: authUrl,
        windowName: "_blank",
        toolbarColor: "#EA4335",
      });
      // The appUrlListener in onMounted will handle the callback
    } else {
      // On web, redirect to OAuth page
      window.location.href = authUrl;
    }
  } catch (err) {
    console.error("Failed to initiate Gmail connection:", err);
    error.value = "Failed to initiate Gmail connection. Please try again.";
  }
};

const connectOutlook = async () => {
  try {
    const authUrl = await connectOutlookAccount();
    const isMobile = Capacitor.isNativePlatform();

    if (isMobile) {
      // Open OAuth in in-app browser on mobile
      await Browser.open({
        url: authUrl,
        windowName: "_blank",
        toolbarColor: "#0078D4",
      });
      // The appUrlListener in onMounted will handle the callback
    } else {
      // On web, redirect to OAuth page
      window.location.href = authUrl;
    }
  } catch (err) {
    console.error("Failed to initiate Outlook connection:", err);
    if (err.response?.status === 503) {
      error.value =
        "Outlook integration is not yet configured. Please contact your administrator.";
    } else {
      error.value = "Failed to initiate Outlook connection. Please try again.";
    }
  }
};

const setPrimary = async (accountId) => {
  try {
    await setPrimaryAccount(accountId);
    await accountsStore.fetchAccounts({ force: true });
    accounts.value = accountsStore.accounts;
  } catch (err) {
    console.error("Failed to set primary:", err);
    error.value = "Failed to set primary account.";
  }
};

const deleteAccount = async (accountId) => {
  if (!confirm("Are you sure you want to disconnect this account?")) {
    return;
  }

  try {
    await deleteEmailAccount(accountId);
    await accountsStore.fetchAccounts({ force: true });
    accounts.value = accountsStore.accounts;
  } catch (err) {
    console.error("Failed to delete account:", err);
    error.value = "Failed to delete account.";
  }
};

const refreshAccounts = async () => {
  loading.value = true;
  error.value = null;
  try {
    await accountsStore.fetchAccounts({ force: true });
    accounts.value = accountsStore.accounts;
  } catch (err) {
    console.error("Failed to refresh accounts:", err);
    error.value = "Failed to refresh accounts. Please try again.";
  } finally {
    loading.value = false;
  }
};

const formatDate = (dateString) => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

onMounted(async () => {
  // Initialize with cached accounts immediately if available
  if (accountsStore.accounts.length > 0) {
    accounts.value = accountsStore.accounts;
  }
  loadAccounts();

  // Set up deep link listener for OAuth callbacks (mobile only)
  if (Capacitor.isNativePlatform()) {
    appUrlListener = await App.addListener("appUrlOpen", async (data) => {
      console.log("[AccountsView] Deep link received:", data.url);

      // Check if this is our OAuth callback - flexible pattern matching
      if (data.url && (data.url.includes("novamind://auth/callback") || data.url.includes("/auth/callback"))) {
        console.log("[AccountsView] OAuth callback detected, redirecting to inbox");

        // Close the in-app browser
        await Browser.close();

        // CRITICAL: Invalidate email cache so inbox will fetch fresh data
        emailCache.invalidateAll();

        // Force reload accounts to get the newly connected account
        await accountsStore.fetchAccounts({ force: true });

        // Redirect to inbox to show fresh emails
        router.push("/app/email/inbox");
      }
    });
  }
});

onUnmounted(() => {
  // Clean up the deep link listener
  if (appUrlListener) {
    appUrlListener.remove();
  }
});
</script>

<style scoped>
.accounts-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  height: 100vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
}

h2 {
  margin-bottom: 1.5rem;
  color: #333;
}

.accounts-header {
  flex-shrink: 0;
  margin-bottom: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.connect-buttons {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.btn-gmail,
.btn-outlook {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-gmail {
  background: #ea4335;
  color: white;
}

.btn-gmail:hover {
  background: #d93025;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 67, 53, 0.3);
}

.btn-outlook {
  background: #0078d4;
  color: white;
}

.btn-outlook:hover {
  background: #106ebe;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
}

.provider-icon {
  width: 20px;
  height: 20px;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: 2px solid var(--primary-color, #6c63ff);
  background: transparent;
  color: var(--primary-color, #6c63ff);
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  transition: all 0.2s;
  align-self: flex-start;
}

.btn-refresh:hover:not(:disabled) {
  background: var(--primary-color, #6c63ff);
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(108, 99, 255, 0.3);
}

.btn-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.refresh-icon {
  width: 20px;
  height: 20px;
  transition: transform 0.3s ease;
}

.refresh-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.loading,
.error {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.error {
  color: #d32f2f;
  background: #ffebee;
  border-radius: 8px;
}

.accounts-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 2rem;
  -webkit-overflow-scrolling: touch;
}

.account-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.account-info {
  flex: 1;
}

.account-email {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.provider-badge {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.provider-badge.gmail {
  background: #fdecea;
  color: #ea4335;
}

.provider-badge.outlook {
  background: #e6f2fb;
  color: #0078d4;
}

.primary-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.75rem;
  background: #4caf50;
  color: white;
  border-radius: 12px;
  font-weight: 500;
}

.account-name {
  margin-bottom: 0.25rem;
}

.account-date {
  font-size: 0.875rem;
}

.account-actions {
  display: flex;
  gap: 0.75rem;
}

.btn-secondary,
.btn-danger {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-secondary {
  background: #e3f2fd;
  color: #1976d2;
}

.btn-secondary:hover {
  background: #bbdefb;
}

.btn-danger {
  background: #ffebee;
  color: #d32f2f;
}

.btn-danger:hover {
  background: #ffcdd2;
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  padding-bottom: 8rem;
}

.empty-state p {
  margin: 1rem 0 0.5rem;
  color: #666;
  font-size: 1.1rem;
}

.empty-hint {
  color: #999 !important;
  font-size: 0.9rem !important;
}

.account-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;

  background: var(--sidebar-bg); /* adapts with theme */
  border: 1px solid var(--border-color); /* adapts with theme */
  border-radius: 8px;
  transition: box-shadow 0.2s;
}

.account-email {
  color: var(--text-primary); /* adapts */
}

.account-name {
  color: var(--text-secondary); /* adapts */
}

.account-date {
  color: var(--text-secondary); /* adapts */
  opacity: 0.75; /* keeps it “subtle” */
}

h2 {
  color: #333;
}

/* Skeleton wrapper */
.accounts-skeleton {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding-bottom: 2rem;
  -webkit-overflow-scrolling: touch;
}

/* Skeleton card uses same base card styling */
.skeleton-card {
  position: relative;
  overflow: hidden;
}

/* Shimmer overlay - simplified for better performance */
.skeleton-card::after {
  content: "";
  position: absolute;
  inset: 0;
  transform: translateX(-100%);
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.15),
    transparent
  );
  animation: shimmer 1.5s ease-in-out infinite;
  pointer-events: none;
}

@keyframes shimmer {
  to {
    transform: translateX(100%);
  }
}

/* Skeleton “lines” */
.skeleton-line {
  height: 12px;
  border-radius: 8px;
  background: var(--hover-bg);
  margin-bottom: 10px;
}

/* widths */
.w-60 {
  width: 60%;
}
.w-40 {
  width: 40%;
}
.w-30 {
  width: 30%;
}

/* Skeleton buttons */
.skeleton-btn {
  width: 110px;
  height: 34px;
  border-radius: 8px;
  background: var(--hover-bg);
}

/* Mobile Optimizations */
@media (max-width: 768px) {
  .accounts-container {
    padding: 1rem;
    padding-bottom: 2rem;
    height: 100vh;
  }

  .accounts-header {
    margin-bottom: 1rem;
  }

  .connect-buttons {
    flex-direction: column;
    gap: 0.75rem;
  }

  .btn-gmail,
  .btn-outlook {
    width: 100%;
    justify-content: center;
    padding: 1rem 1.5rem;
    font-size: 1.05rem;
    min-height: 52px;
  }

  .btn-refresh {
    width: 100%;
    justify-content: center;
    padding: 0.9rem 1.5rem;
    font-size: 1rem;
    min-height: 48px;
  }

  .account-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 1.25rem;
    padding: 1.25rem;
  }

  .account-info {
    width: 100%;
  }

  .account-email {
    font-size: 1rem;
    flex-wrap: wrap;
  }

  .account-actions {
    width: 100%;
    flex-direction: column;
    gap: 0.5rem;
  }

  .btn-secondary,
  .btn-danger {
    width: 100%;
    justify-content: center;
    padding: 0.75rem 1rem;
    font-size: 0.95rem;
    min-height: 44px;
  }

  .provider-badge {
    font-size: 0.65rem;
    padding: 0.25rem 0.6rem;
  }

  .primary-badge {
    font-size: 0.7rem;
    padding: 0.3rem 0.8rem;
  }
}

/* Extra small screens */
@media (max-width: 480px) {
  .accounts-container {
    padding: 0.75rem;
    padding-bottom: 2rem;
    height: 100vh;
  }

  .account-card {
    padding: 1rem;
  }

  .account-email {
    font-size: 0.95rem;
  }

  .account-name,
  .account-date {
    font-size: 0.85rem;
  }
}
</style>
