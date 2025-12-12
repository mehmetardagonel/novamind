<template>
  <div class="accounts-container">
    <h2>Gmail Hesapları</h2>

    <button @click="connectAccount" class="btn-connect">
      <i class="pi pi-plus"></i>
      Yeni Hesap Bağla
    </button>

    <div v-if="loading" class="loading">Yükleniyor...</div>

    <div v-else-if="error" class="error">{{ error }}</div>

    <div v-else class="accounts-list">
      <div v-for="account in accounts" :key="account.id" class="account-card">
        <div class="account-info">
          <div class="account-email">
            {{ account.email_address }}
            <span v-if="account.is_primary" class="primary-badge">Birincil</span>
          </div>
          <div class="account-name">{{ account.display_name }}</div>
          <div class="account-date">Bağlandı: {{ formatDate(account.created_at) }}</div>
        </div>

        <div class="account-actions">
          <button
            v-if="!account.is_primary"
            @click="setPrimary(account.id)"
            class="btn-secondary"
          >
            Birincil Yap
          </button>

          <button
            @click="deleteAccount(account.id)"
            class="btn-danger"
          >
            <i class="pi pi-trash"></i>
            Bağlantıyı Kes
          </button>
        </div>
      </div>

      <div v-if="accounts.length === 0" class="empty-state">
        <i class="pi pi-inbox" style="font-size: 3rem; color: #ccc;"></i>
        <p>Henüz bağlı Gmail hesabı yok</p>
        <button @click="connectAccount" class="btn-connect">
          İlk Hesabı Bağla
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import {
  fetchGmailAccounts,
  connectGmailAccount,
  setPrimaryAccount,
  deleteGmailAccount
} from '../api/accounts';

const accounts = ref([]);
const loading = ref(true);
const error = ref(null);

const loadAccounts = async () => {
  loading.value = true;
  error.value = null;
  try {
    accounts.value = await fetchGmailAccounts();
  } catch (err) {
    console.error('Failed to load accounts:', err);
    error.value = 'Hesaplar yüklenemedi. Lütfen tekrar deneyin.';
  } finally {
    loading.value = false;
  }
};

const connectAccount = async () => {
  try {
    const authUrl = await connectGmailAccount();
    // Redirect to Google OAuth
    window.location.href = authUrl;
  } catch (err) {
    console.error('Failed to initiate connection:', err);
    error.value = 'Bağlantı başlatılamadı. Lütfen tekrar deneyin.';
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
    await deleteGmailAccount(accountId);
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

onMounted(() => {
  loadAccounts();
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
  color: #333;
}

.btn-connect {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: #1976d2;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 1rem;
  margin-bottom: 2rem;
  transition: background 0.2s;
}

.btn-connect:hover {
  background: #1565c0;
}

.loading,
.error {
  text-align: center;
  padding: 2rem;
  color: #666;
}

.error {
  color: #d32f2f;
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
  background: white;
  border: 1px solid #e0e0e0;
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
  color: #333;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
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
}

.empty-state p {
  margin: 1rem 0 2rem;
  color: #666;
  font-size: 1.1rem;
}
</style>
