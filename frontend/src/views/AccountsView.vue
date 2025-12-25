<template>
  <div class="accounts-container">
    <h2>Email Accounts</h2>

    <!-- Connection Buttons -->
    <div class="connect-buttons">
      <button @click="connectGmail" class="btn-gmail">
        <svg class="provider-icon" viewBox="0 0 24 24" width="20" height="20">
          <path fill="currentColor" d="M20,18H18V9.25L12,13L6,9.25V18H4V6H5.2L12,10.25L18.8,6H20M20,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V6C22,4.89 21.1,4 20,4Z"/>
        </svg>
        Connect Gmail Account
      </button>

      <button @click="connectOutlook" class="btn-outlook">
        <svg class="provider-icon" viewBox="0 0 24 24" width="20" height="20">
          <path fill="currentColor" d="M22,4H14V7H22V4M22,8H14V11H22V8M22,12H14V15H22V12M22,16H14V19H22V16M12,4A2,2 0 0,0 10,6V18A2,2 0 0,0 12,20H13V4H12M4,4A2,2 0 0,0 2,6V18A2,2 0 0,0 4,20H11V4H4M8.5,10.5L9.5,8.5L10.5,10.5L12.5,11.5L10.5,12.5L9.5,14.5L8.5,12.5L6.5,11.5L8.5,10.5Z"/>
        </svg>
        Connect Outlook Account
      </button>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="accounts-list">
      <div v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-info">
          <div class="account-email">
            <span :class="['provider-badge', account.provider || 'gmail']">
              {{ (account.provider || 'gmail') === 'gmail' ? 'GMAIL' : 'OUTLOOK' }}
            </span>
            {{ account.email_address }}
            <span v-if="account.is_primary" class="primary-badge">Primary</span>
          </div>
          <div class="account-name">{{ account.display_name }}</div>
          <div class="account-date">Connected: {{ formatDate(account.created_at) }}</div>
        </div>

        <div class="account-actions">
          <button
            v-if="!account.is_primary"
            @click="setPrimary(account.id)"
            class="btn-secondary"
          >
            Set as Primary
          </button>

          <button
            @click="deleteAccount(account.id)"
            class="btn-danger"
          >
            <i class="pi pi-trash"></i>
            Disconnect
          </button>
        </div>
      </div>

      <div v-if="accounts.length === 0" class="empty-state">
        <i class="pi pi-inbox" style="font-size: 3rem; color: #ccc;"></i>
        <p>No connected email accounts yet</p>
        <p class="empty-hint">Connect your Gmail or Outlook account to get started</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import {
  fetchEmailAccounts,
  connectGmailAccount,
  connectOutlookAccount,
  setPrimaryAccount,
  deleteEmailAccount
} from '../api/accounts';
import { Browser } from '@capacitor/browser';
import { App } from '@capacitor/app';
import { Capacitor } from '@capacitor/core';

const accounts = ref([]);
const loading = ref(true);
const error = ref(null);

const loadAccounts = async () => {
  loading.value = true;
  error.value = null;
  try {
    accounts.value = await fetchEmailAccounts();
  } catch (err) {
    console.error('Failed to load accounts:', err);
    error.value = 'Hesaplar yüklenemedi. Lütfen tekrar deneyin.';
  } finally {
    loading.value = false;
  }
};

const connectGmail = async () => {
  try {
    const authUrl = await connectGmailAccount();

    // Check if running on mobile (Capacitor native platform)
    const isMobile = Capacitor.isNativePlatform();

    if (isMobile) {
      // Mobile: Open in-app browser
      await Browser.open({
        url: authUrl,
        windowName: '_blank',
        toolbarColor: '#EA4335'
      });
    } else {
      // Web: Traditional redirect
      window.location.href = authUrl;
    }
  } catch (err) {
    console.error('Failed to initiate Gmail connection:', err);
    error.value = 'Gmail bağlantısı başlatılamadı. Lütfen tekrar deneyin.';
  }
};

const connectOutlook = async () => {
  try {
    const authUrl = await connectOutlookAccount();

    // Check if running on mobile (Capacitor native platform)
    const isMobile = Capacitor.isNativePlatform();

    if (isMobile) {
      // Mobile: Open in-app browser
      await Browser.open({
        url: authUrl,
        windowName: '_blank',
        toolbarColor: '#0078D4'
      });
    } else {
      // Web: Traditional redirect
      window.location.href = authUrl;
    }
  } catch (err) {
    console.error('Failed to initiate Outlook connection:', err);
    if (err.response?.status === 503) {
      error.value = 'Outlook entegrasyonu henüz yapılandırılmamış. Lütfen yöneticinize başvurun.';
    } else {
      error.value = 'Outlook bağlantısı başlatılamadı. Lütfen tekrar deneyin.';
    }
  }
};

const setPrimary = async (accountId) => {
  try {
    await setPrimaryAccount(accountId);
    await loadAccounts();
  } catch (err) {
    console.error('Failed to set primary:', err);
    error.value = 'Birincil hesap ayarlanamadı.';
  }
};

const deleteAccount = async (accountId) => {
  if (!confirm('Bu hesabın bağlantısını kesmek istediğinize emin misiniz?')) {
    return;
  }

  try {
    await deleteEmailAccount(accountId);
    await loadAccounts();
  } catch (err) {
    console.error('Failed to delete account:', err);
    error.value = 'Hesap silinemedi.';
  }
};

const formatDate = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('tr-TR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  });
};

let appUrlListener = null;

onMounted(async () => {
  await loadAccounts();

  // Setup deep link listener for mobile OAuth callback
  if (Capacitor.isNativePlatform()) {
    appUrlListener = await App.addListener('appUrlOpen', async (data) => {
      console.log('Deep link received:', data.url);

      // Check if this is an OAuth callback (Gmail or Outlook)
      if (data.url.includes('novamind://auth/callback') || data.url.includes('/auth/callback')) {
        console.log('OAuth callback detected, closing browser and refreshing accounts');

        // Close the in-app browser
        await Browser.close();

        // Refresh accounts list
        await loadAccounts();
      }
    });
  }
});

onUnmounted(() => {
  // Clean up listener
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
}

h2 {
  margin-bottom: 1.5rem;
  color: var(--text-primary, #333);
}

.connect-buttons {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
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
  min-height: 44px; /* Touch-friendly */
}

.btn-gmail {
  background: #EA4335;
  color: white;
}

.btn-gmail:hover {
  background: #D93025;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 67, 53, 0.3);
}

.btn-outlook {
  background: #0078D4;
  color: white;
}

.btn-outlook:hover {
  background: #106EBE;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
}

.provider-icon {
  width: 20px;
  height: 20px;
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
}

.account-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  background: var(--content-bg, white);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  transition: box-shadow 0.2s;
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
  color: var(--text-primary, #333);
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
  background: #FDECEA;
  color: #EA4335;
}

.provider-badge.outlook {
  background: #E6F2FB;
  color: #0078D4;
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
  color: #666;
  margin-bottom: 0.25rem;
}

.account-date {
  font-size: 0.875rem;
  color: #999;
}

.account-actions {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
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
  min-height: 44px; /* Touch-friendly */
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

/* Mobile Responsive */
@media (max-width: 768px) {
  .accounts-container {
    padding: 1rem;
  }

  .connect-buttons {
    flex-direction: column;
  }

  .btn-gmail,
  .btn-outlook {
    width: 100%;
    justify-content: center;
  }

  .account-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .account-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .account-email {
    font-size: 1rem;
  }
}

@media (max-width: 480px) {
  h2 {
    font-size: 1.5rem;
  }

  .btn-gmail,
  .btn-outlook {
    font-size: 0.9rem;
    padding: 0.65rem 1.25rem;
  }

  .account-actions {
    flex-direction: column;
    width: 100%;
  }

  .btn-secondary,
  .btn-danger {
    width: 100%;
    justify-content: center;
  }
}
</style>
