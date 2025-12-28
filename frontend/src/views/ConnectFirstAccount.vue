<template>
  <div class="app-screen">
    <div
      class="background-image"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }"
    ></div>
    <div class="background-overlay"></div>

    <div class="content-wrapper">
      <main class="connect-container">
        <div class="connect-header">
          <div class="header-logo-wrapper">
            <div class="logo-icon-container">
              <div class="logo-svg novamind-logo">
                <svg
                  fill="none"
                  viewBox="0 0 48 48"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"
                    fill="currentColor"
                  ></path>
                </svg>
              </div>
            </div>

            <h1 class="logo-text">Novamind.AI</h1>
          </div>
          <p class="header-title">Connect your first email account</p>
          <p class="header-subtitle">To get started, connect Gmail or Outlook.</p>
        </div>

        <div class="connect-actions">
          <button
            class="provider-button gmail"
            type="button"
            :disabled="actionLoading"
            @click="connectGmail"
          >
            Connect Gmail
          </button>
          <button
            class="provider-button outlook"
            type="button"
            :disabled="actionLoading"
            @click="connectOutlook"
          >
            Connect Outlook
          </button>
        </div>

        <p v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </p>

        <p class="note-text">
          You can connect more accounts later from Accounts.
        </p>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import BackgroundImage from "@/assets/background.png";
import { useAccountsStore } from "@/stores/accounts";
import { connectGmailAccount, connectOutlookAccount } from "@/api/accounts";
import {
  setForceMailboxLoading,
  shouldForceMailboxLoading,
  clearForceMailboxLoading,
} from "@/utils/navigationFlags";

const router = useRouter();
const accountsStore = useAccountsStore();
const backgroundImageUrl = BackgroundImage;
const errorMessage = ref("");
const actionLoading = ref(false);

const connectDebug = import.meta.env.VITE_CONNECT_DEBUG === "1";

const redirectIfConnected = () => {
  if (!accountsStore.hasConnectedAccounts) {
    clearForceMailboxLoading();
    return;
  }

  const shouldGoToLoading = shouldForceMailboxLoading();
  clearForceMailboxLoading();

  if (connectDebug) {
    console.info(
      `CONNECT_DEBUG: redirecting to ${shouldGoToLoading ? "/mailbox-loading" : "/app/email/inbox"} from ConnectFirstAccount`
    );
  }

  router.replace(shouldGoToLoading ? "/mailbox-loading" : "/app/email/inbox");
};

const refreshAccounts = async () => {
  await accountsStore.fetchAccounts({ force: true });
  redirectIfConnected();
};

const startConnectFlow = async (providerConnect) => {
  errorMessage.value = "";
  actionLoading.value = true;
  try {
    sessionStorage.setItem("oauth_redirect_path", "/connect-first-account");
    setForceMailboxLoading();

    const authUrl = await providerConnect();
    window.location.href = authUrl;
  } catch (err) {
    console.error("Failed to initiate connection:", err);
    clearForceMailboxLoading();
    sessionStorage.removeItem("oauth_redirect_path");
    errorMessage.value = "Could not start connection. Please try again.";
    actionLoading.value = false;
  }
};

const connectGmail = async () => {
  await startConnectFlow(connectGmailAccount);
};

const connectOutlook = async () => {
  errorMessage.value = "";
  actionLoading.value = true;
  try {
    sessionStorage.setItem("oauth_redirect_path", "/connect-first-account");
    setForceMailboxLoading();

    const authUrl = await connectOutlookAccount();
    window.location.href = authUrl;
  } catch (err) {
    console.error("Failed to initiate Outlook connection:", err);
    clearForceMailboxLoading();
    sessionStorage.removeItem("oauth_redirect_path");

    if (err.response?.status === 503) {
      errorMessage.value =
        "Outlook integration is not yet configured. Please contact your administrator.";
    } else {
      errorMessage.value = "Could not start connection. Please try again.";
    }
    actionLoading.value = false;
  }
};

watch(
  () => accountsStore.accounts.length,
  (nextLength) => {
    if (nextLength > 0) {
      redirectIfConnected();
    }
  }
);

onMounted(async () => {
  await refreshAccounts();
});
</script>

<style scoped>
.app-screen {
  position: relative;
  display: flex;
  min-height: 100vh;
  width: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--background-light);
  overflow: hidden;
}

.background-image {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
}

.background-overlay {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-color: rgba(19, 16, 34, 0.5);
}

.content-wrapper {
  position: relative;
  z-index: 10;
  display: flex;
  width: 100%;
  max-width: 28rem;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
}

.connect-container {
  width: 100%;
  max-width: 28rem;
  min-height: 24rem;
  border-radius: 0.75rem;
  border: 1px solid var(--primary-border-10);
  background-color: #ffffff;
  padding: 2.5rem;
  box-shadow: 0 25px 50px -12px var(--primary-shadow-10);
  box-sizing: border-box;
  position: relative;
  text-align: center;
}

.connect-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}

.header-logo-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.logo-icon-container {
  position: relative;
  width: 2rem;
  height: 2rem;
}

.logo-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  color: var(--primary-color);
}

.logo-text {
  font-size: 1.875rem;
  line-height: 2.25rem;
  font-weight: 700;
  letter-spacing: -0.025em;
  margin: 0;
  color: var(--text-primary);
}

.header-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 1rem 0 0;
}

.header-subtitle {
  text-align: center;
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 0 0 1.5rem;
}

.connect-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.provider-button {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 3rem;
  width: 100%;
  border-radius: 0.5rem;
  border: none;
  font-size: 1rem;
  font-weight: 700;
  cursor: pointer;
  color: #ffffff;
  transition: all 0.2s ease-in-out;
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30);
}

.provider-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
}

.provider-button.gmail {
  background: #ea4335;
}

.provider-button.gmail:hover:not(:disabled) {
  background: #d93025;
  transform: translateY(-1px);
}

.provider-button.outlook {
  background: #0078d4;
}

.provider-button.outlook:hover:not(:disabled) {
  background: #106ebe;
  transform: translateY(-1px);
}

.error-message {
  margin: 0 0 0.75rem;
  color: #d32f2f;
  background: #ffebee;
  border-radius: 0.5rem;
  padding: 0.75rem 1rem;
  font-size: 0.95rem;
}

.note-text {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

@media (max-width: 480px) {
  .connect-container {
    padding: 2rem;
  }
}
</style>
