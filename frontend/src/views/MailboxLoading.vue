<template>
  <div class="app-screen">
    <div
      class="background-image"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }"
    ></div>
    <div class="background-overlay"></div>

    <div class="content-wrapper">
      <main class="loading-container">
        <div class="loading-header">
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
          <p class="header-title">Loading emails...</p>
          <p class="header-subtitle">Syncing your mailbox</p>
        </div>

        <div class="progress-wrapper" v-if="!showError">
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: bootPercent + '%' }"
            ></div>
          </div>
          <div class="progress-text">
            {{ bootPercent }}%
          </div>
          <img class="mail-loading-gif" :src="mailGif" alt="" />
        </div>

        <div v-else class="error-state">
          <p class="error-message">
            {{ bootErrorMessage || "We couldn't load your mailbox. Please try again." }}
          </p>
          <button class="primary-button" type="button" @click="retryPrefetch">
            Retry
          </button>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import BackgroundImage from "@/assets/background.png";
import mailGif from "@/assets/mail.gif";
import { useEmailCacheStore } from "@/stores/emails";
import { useAccountsStore } from "@/stores/accounts";

export default {
  name: "MailboxLoading",
  setup() {
    const router = useRouter();
    const emailCache = useEmailCacheStore();
    const accountsStore = useAccountsStore();
    const { bootStatus, bootPercent, bootErrorMessage } = storeToRefs(emailCache);

    const backgroundImageUrl = BackgroundImage;
    const showError = computed(() => bootStatus.value === "error");

    const routeToDestination = () => {
      router.replace("/app/email/inbox");
    };

    const ensureAccountsAndPrefetch = async ({ force = false } = {}) => {
      await accountsStore.fetchAccounts({ force });
      if (!accountsStore.hasConnectedAccounts) {
        router.replace("/connect-first-account");
        return;
      }

      await emailCache.prefetchMailboxAfterLogin({ force });
      if (emailCache.bootStatus === "ready") {
        routeToDestination();
      }
    };

    const retryPrefetch = async () => {
      await ensureAccountsAndPrefetch({ force: true });
    };

    onMounted(async () => {
      await ensureAccountsAndPrefetch();
    });

    return {
      backgroundImageUrl,
      mailGif,
      bootPercent,
      bootErrorMessage,
      showError,
      retryPrefetch,
    };
  },
};
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

.loading-container {
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

.loading-header {
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

.progress-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.progress-bar {
  height: 0.6rem;
  width: 100%;
  border-radius: 999px;
  background: #eef0f7;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  width: 0%;
  border-radius: 999px;
  background: var(--primary-color);
  transition: width 0.2s ease;
}

.progress-text {
  font-size: 0.95rem;
  color: var(--text-secondary);
}

.mail-loading-gif {
  display: block;
  margin: 14px auto 0;
  width: 84px;
  height: auto;
  animation: mailGifBounce 1.3s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  will-change: transform;
}

@keyframes mailGifBounce {
  0%,
  100% {
    transform: translateY(0px);
  }
  50% {
    transform: translateY(8px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .mail-loading-gif {
    animation: none !important;
  }
}

.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  margin-top: 1.5rem;
}

.error-message {
  color: var(--text-secondary);
  margin: 0;
}

.primary-button {
  display: flex;
  height: 3rem;
  width: 100%;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  background-color: var(--primary-color);
  padding: 0.75rem 1.5rem;
  font-size: 1rem;
  font-weight: 700;
  color: #ffffff;
  border: none;
  cursor: pointer;
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30);
  transition: all 0.2s ease-in-out;
}

.primary-button:hover {
  opacity: 0.9;
}
</style>
