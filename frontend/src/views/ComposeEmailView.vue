<template>
  <div class="compose-email-view">
    <div v-if="!hasConnectedAccounts" class="compose-empty">
      <div class="compose-empty-card">
        <span class="material-symbols-outlined empty-icon">mail</span>
        <h2>Connect an account to send emails</h2>
        <p>Once you link a Gmail or Outlook account, you can compose messages here.</p>
        <button class="btn btn-primary" type="button" @click="goToAccounts">
          Go to Accounts
        </button>
      </div>
    </div>

    <div v-else class="compose-card">
      <form class="compose-form" @submit.prevent="handleSend">
        <div class="form-row">
          <label for="compose-account">From</label>
          <select
            id="compose-account"
            v-model="activeAccountId"
            class="form-select"
            :disabled="formDisabled"
          >
            <option v-for="account in accounts" :key="account.id" :value="account.id">
              {{ formatAccountLabel(account) }}
            </option>
          </select>
        </div>

        <div class="form-row">
          <label for="compose-to">To <span class="required">*</span></label>
          <input
            id="compose-to"
            v-model="to"
            type="text"
            class="form-input"
            placeholder="recipient@example.com"
            :disabled="formDisabled"
            @input="clearStatus"
          />
          <p v-if="toError" class="form-error">{{ toError }}</p>
        </div>

        <div class="form-row">
          <label for="compose-subject">Subject</label>
          <input
            id="compose-subject"
            v-model="subject"
            type="text"
            class="form-input"
            placeholder="Add a subject"
            :disabled="formDisabled"
            @input="clearStatus"
          />
        </div>

        <div class="form-row">
          <label for="compose-body">Body <span class="required">*</span></label>
          <textarea
            id="compose-body"
            v-model="body"
            class="form-textarea"
            placeholder="Write your email..."
            :disabled="formDisabled"
            @input="clearStatus"
          ></textarea>
          <p v-if="bodyError" class="form-error">{{ bodyError }}</p>
        </div>

        <div v-if="statusMessage" :class="['compose-alert', statusType]">
          {{ statusMessage }}
        </div>

        <div class="form-actions">
          <button
            type="button"
            class="btn btn-secondary"
            :disabled="formDisabled"
            @click="handleSaveDraft"
          >
            {{ isSaving ? "Saving..." : "Save Draft" }}
          </button>
          <button
            type="submit"
            class="btn btn-primary"
            :disabled="formDisabled"
          >
            {{ isSending ? "Sending..." : "Send" }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { storeToRefs } from "pinia";
import { useAccountsStore } from "../stores/accounts";
import { sendEmail, saveDraft } from "../api/emails";

export default {
  name: "ComposeEmailView",
  props: {
    selectedAccountId: {
      type: String,
      default: null,
    },
  },
  setup(props) {
    const router = useRouter();
    const accountsStore = useAccountsStore();
    const { accounts, hasConnectedAccounts } = storeToRefs(accountsStore);

    const activeAccountId = ref(props.selectedAccountId);
    const to = ref("");
    const subject = ref("");
    const body = ref("");
    const toError = ref("");
    const bodyError = ref("");
    const statusMessage = ref("");
    const statusType = ref("");
    const isSending = ref(false);
    const isSaving = ref(false);

    const formDisabled = computed(() => !hasConnectedAccounts.value || isSending.value || isSaving.value);

    const selectedAccount = computed(() =>
      accounts.value.find((account) => account.id === activeAccountId.value)
    );

    const defaultAccountId = computed(() => {
      if (!accounts.value.length) return null;
      const primary = accounts.value.find((account) => account.is_primary);
      return primary ? primary.id : accounts.value[0].id;
    });

    const formatAccountLabel = (account) => {
      const provider = account.provider === "gmail" ? "Gmail" : "Outlook";
      return `${provider} - ${account.email_address}`;
    };

    const clearStatus = () => {
      statusMessage.value = "";
      statusType.value = "";
    };

    const validateForm = () => {
      toError.value = "";
      bodyError.value = "";

      const recipients = to.value
        .split(",")
        .map((entry) => entry.trim())
        .filter(Boolean);

      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (recipients.length === 0) {
        toError.value = "Please enter at least one recipient.";
      } else if (recipients.some((entry) => !emailRegex.test(entry))) {
        toError.value = "Enter valid email addresses separated by commas.";
      }

      if (!body.value.trim()) {
        bodyError.value = "Email body is required.";
      }

      return !toError.value && !bodyError.value;
    };

    const handleSaveDraft = async () => {
      if (!validateForm()) {
        return;
      }

      clearStatus();
      isSaving.value = true;
      try {
        await saveDraft({
          to: to.value.trim(),
          subject: subject.value.trim(),
          body: body.value.trim(),
          accountId: activeAccountId.value,
          provider: selectedAccount.value?.provider,
        });
        statusMessage.value = "Draft saved successfully.";
        statusType.value = "success";
      } catch (error) {
        console.error("Save draft failed:", error);
        statusMessage.value = "Could not save draft. Please try again.";
        statusType.value = "error";
      } finally {
        isSaving.value = false;
      }
    };

    const handleSend = async () => {
      if (!validateForm()) {
        return;
      }

      clearStatus();
      isSending.value = true;
      try {
        await sendEmail({
          to: to.value.trim(),
          subject: subject.value.trim(),
          body: body.value.trim(),
          accountId: activeAccountId.value,
          provider: selectedAccount.value?.provider,
        });
        statusMessage.value = "Email sent successfully.";
        statusType.value = "success";
        to.value = "";
        subject.value = "";
        body.value = "";
      } catch (error) {
        console.error("Send email failed:", error);
        statusMessage.value = "Could not send email. Please try again.";
        statusType.value = "error";
      } finally {
        isSending.value = false;
      }
    };

    const goToAccounts = () => {
      router.push("/app/accounts");
    };

    onMounted(async () => {
      if (!accounts.value.length) {
        await accountsStore.fetchAccounts();
      }
    });

    watch(
      () => accounts.value,
      () => {
        if (!activeAccountId.value) {
          activeAccountId.value = defaultAccountId.value;
        }
      },
      { immediate: true }
    );

    watch(
      () => props.selectedAccountId,
      (newValue) => {
        if (newValue) {
          activeAccountId.value = newValue;
        }
      }
    );

    return {
      accounts,
      hasConnectedAccounts,
      activeAccountId,
      to,
      subject,
      body,
      toError,
      bodyError,
      statusMessage,
      statusType,
      isSending,
      isSaving,
      formDisabled,
      formatAccountLabel,
      handleSend,
      handleSaveDraft,
      clearStatus,
      goToAccounts,
    };
  },
};
</script>

<style scoped>
.compose-email-view {
  height: 100%;
  padding: 2rem;
  overflow-y: auto;
}

.compose-card {
  max-width: 760px;
  margin: 0 auto;
  background: var(--content-bg);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
}

.compose-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

label {
  font-weight: 600;
  color: var(--text-primary);
}

.required {
  color: var(--danger-color);
}

.form-input,
.form-textarea,
.form-select {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 0.95rem;
  background: var(--content-bg);
  color: var(--text-primary);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-textarea {
  min-height: 220px;
  resize: vertical;
}

.form-input:focus,
.form-textarea:focus,
.form-select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(108, 99, 255, 0.15);
}

.form-error {
  color: var(--danger-color);
  font-size: 0.85rem;
}

.compose-alert {
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 0.95rem;
}

.compose-alert.success {
  background: rgba(46, 204, 113, 0.12);
  color: #1b7f3a;
}

.compose-alert.error {
  background: rgba(231, 76, 60, 0.12);
  color: #b93a2b;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 6px;
}

.btn {
  border: none;
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
  box-shadow: none;
  transform: none;
}

.btn-primary {
  background: var(--primary-color);
  color: var(--text-on-primary);
  box-shadow: 0 8px 18px rgba(108, 99, 255, 0.25);
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover-color);
  transform: translateY(-1px);
}

.btn-secondary {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
  border-color: var(--primary-color);
  color: var(--primary-color);
}

.compose-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.compose-empty-card {
  max-width: 520px;
  text-align: center;
  padding: 2.5rem;
  border-radius: 18px;
  border: 1px dashed var(--border-color);
  background: var(--content-bg);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.05);
}

.compose-empty-card h2 {
  margin: 0.5rem 0 0.75rem;
  color: var(--text-primary);
}

.compose-empty-card p {
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}

.empty-icon {
  font-size: 36px;
  color: var(--primary-color);
}

@media (max-width: 768px) {
  .compose-email-view {
    padding: 1.5rem;
  }

  .compose-card {
    padding: 20px;
  }

  .form-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
