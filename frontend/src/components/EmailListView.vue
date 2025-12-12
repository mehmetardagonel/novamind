<template>
  <div class="email-list-view">
    <div v-if="loading" class="loading">
      <p>Loading emails...</p>
    </div>

    <div v-else-if="authUrl" class="auth-prompt">
      <h2>Gmail Authentication Required</h2>
      <p>Please connect your Google account to fetch emails.</p>
      <button @click="authenticate" class="btn btn-primary">
        Connect with Google
      </button>
      <p v-if="errorMessage" class="text-danger mt-3">
        Error: {{ errorMessage }}
      </p>
    </div>

    <div v-else-if="errorMessage" class="error-box">
      <h3>Gmail API Error</h3>
      <p>{{ errorMessage }}</p>
      <div class="setup-instructions">
        <p><strong>Troubleshooting:</strong></p>
        <ol>
          <li>Ensure backend is running.</li>
          <li>Ensure <code>.env</code> file is correct.</li>
          <li>
            If auth fails, try deleting <code>token.json</code> and
            re-authenticating.
          </li>
        </ol>
      </div>
    </div>

    <div
      v-else-if="emails.length > 0"
      class="email-container"
      :class="{ 'has-detail': selectedEmail && !isTrash }"
    >
      <div
        class="email-list-panel"
        :class="{
          'hide-on-mobile': selectedEmail && !isTrash,
          'full-width': !selectedEmail || isTrash,
        }"
      >
        <div class="email-list">
          <div
            v-for="(email, index) in emails"
            :key="index"
            class="email-item"
            :class="{
              unread: email.isUnread,
              selected: email === selectedEmail,
            }"
            @click="!isTrash && selectEmail(email)"
          >
            <div class="email-header">
              <div class="sender-with-label">
                <span class="email-sender">{{ email.sender }}</span>
                <span v-if="email.account_email" class="account-badge" :title="email.account_email">
                  {{ email.account_email }}
                </span>
                <span v-if="email.ml_prediction"
                      class="ml-label"
                      :class="'ml-label-' + email.ml_prediction">
                  {{ getLabelText(email.ml_prediction) }}
                </span>
              </div>
              <span class="email-date">{{ formatDate(email.date) }}</span>
            </div>
            <div class="email-subject">{{ email.subject }}</div>
            <div class="email-preview">{{ getPreview(email.body) }}</div>
            <div class="email-actions-bottom" v-if="isTrash">
              <button
                class="icon-action-btn restore-btn"
                title="Restore email"
                @click.stop="handleRestore(email)"
              >
                <span class="material-symbols-outlined"
                  >restore_from_trash</span
                >
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="email-detail-panel" v-if="selectedEmail && !isTrash">
        <div class="email-detail-header">
          <button
            @click="closeEmail"
            class="icon-action-btn"
            title="Back to list"
          >
            <span class="material-symbols-outlined">arrow_back</span>
          </button>

          <div class="email-actions" v-if="!isTrash">
            <!-- Wrap label button + popover together -->
            <div class="label-menu-wrapper">
              <button
                class="icon-action-btn"
                title="Add label"
                @click.stop="toggleLabelMenu"
              >
                <span class="material-symbols-outlined">label</span>
              </button>

              <!-- Small popover right under the button -->
              <div v-if="showLabelMenu" class="label-menu-popover">
                <h3 class="label-menu-title">Labels</h3>

                <p v-if="labelMenuLoading" class="label-menu-status">
                  Loading labels...
                </p>

                <p v-if="labelMenuError" class="label-menu-error">
                  {{ labelMenuError }}
                </p>

                <div
                  v-if="
                    !labelMenuLoading &&
                    !labelMenuError &&
                    availableLabels.length === 0
                  "
                  class="label-menu-empty"
                >
                  No labels yet. You can create them in the Labels tab.
                </div>

                <ul
                  v-if="!labelMenuLoading && availableLabels.length > 0"
                  class="label-menu-list"
                >
                  <li
                    v-for="lab in availableLabels"
                    :key="lab.id"
                    class="label-menu-row"
                  >
                    <label class="label-checkbox-row">
                      <input
                        type="checkbox"
                        :value="lab.id"
                        v-model="selectedLabelIds"
                      />
                      <span class="label-name">{{ lab.name }}</span>
                    </label>
                  </li>
                </ul>

                <div class="label-menu-footer">
                  <div class="label-menu-footer">
                    <button
                      type="button"
                      class="label-btn label-btn-cancel"
                      @click="closeLabelMenu"
                      :disabled="savingLabels"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      class="label-btn label-btn-apply"
                      @click="saveLabelChanges"
                      :disabled="savingLabels"
                    >
                      <span v-if="savingLabels">Saving…</span>
                      <span v-else>Apply</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <button
              class="icon-action-btn"
              v-if="!isTrash && selectedEmail"
              @click.stop="handleFavorite(selectedEmail)"
              title="Star"
            >
              <span
                :class="[
                  'material-symbols-outlined star-toggle',
                  selectedEmail.isStarred ? 'star-filled' : 'star-normal',
                ]"
              >
                star
              </span>
            </button>

            <button
              class="icon-action-btn"
              title="Delete"
              @click.stop="handleDelete"
            >
              <span class="material-symbols-outlined">delete</span>
            </button>
          </div>
        </div>

        <div class="email-detail-content">
          <h2 class="email-detail-subject">{{ selectedEmail.subject }}</h2>

          <div class="email-detail-meta">
            <div class="sender-info">
              <div class="sender-details">
                <div class="sender-name">{{ selectedEmail.sender }}</div>
                <div class="email-date-full">
                  {{ formatFullDate(selectedEmail.date) }}
                </div>
                <div v-if="selectedEmail.account_email" class="account-info">
                  <span class="account-badge">{{ selectedEmail.account_email }}</span>
                </div>
              </div>
            </div>
          </div>

          <div
            class="email-body"
            v-html="sanitizeHtml(selectedEmail.body)"
          ></div>
        </div>
      </div>
    </div>

    <div
      v-if="!loading && !authUrl && !errorMessage && emails.length === 0"
      class="no-emails"
    >
      <p>No emails found.</p>
    </div>
  </div>
</template>

<script>
import { onMounted, ref, watch, computed } from "vue";
import { useRoute } from "vue-router";
import {
  fetchEmails,
  fetchUnifiedEmails,
  deleteEmail,
  setEmailStar,
  restoreEmail,
  fetchLabels,
  updateEmailLabels,
  getEmailsByLabel,
} from "../api/emails";

export default {
  name: "EmailListView",
  props: {
    folder: {
      type: String,
      required: true,
      default: "inbox",
    },
    selectedAccountId: {
      type: String,
      default: null,
    },
    // Removed emailsPerPage prop
  },
  setup(props) {
    const emails = ref([]);
    const loading = ref(false);
    const errorMessage = ref("");
    const selectedEmail = ref(null);
    const authUrl = ref("");
    const isTrash = computed(() => props.folder === "trash");

    const route = useRoute();
    const activeLabelId = computed(() => route.query.label || null);

    // 🔹 label popup state
    const showLabelMenu = ref(false);
    const availableLabels = ref([]);
    const labelMenuLoading = ref(false);
    const labelMenuError = ref("");
    const savingLabels = ref(false);
    const selectedLabelIds = ref([]);

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

    const loadEmails = async () => {
      loading.value = true;
      errorMessage.value = "";
      emails.value = [];
      selectedEmail.value = null;
      authUrl.value = "";

      try {
        let data;
        const labelId = route.query.label; // e.g. "Label_20"

        if (labelId) {
          // We are in a label view: /app/email/inbox?label=Label_20&labelName=Work
          // → use dedicated label endpoint (by label ID)
          data = await getEmailsByLabel(labelId);
        } else if (props.folder === "inbox") {
          // Unified inbox - fetch emails from all connected Gmail accounts
          // Pass selectedAccountId to filter by specific account if selected
          data = await fetchUnifiedEmails(null, props.selectedAccountId);
        } else {
          // Sent / Favorites / Important / Spam / Drafts / Trash
          data = await fetchEmails(props.folder);
        }

        emails.value = decorateEmails(data);
      } catch (error) {
        console.error(`Error fetching ${props.folder} emails:`, error);
        const hasResponse = !!error.response;

        if (!hasResponse) {
          errorMessage.value =
            "Cannot reach the backend API. Make sure the FastAPI server is running.";
        } else if (
          error.response.status === 401 &&
          error.response.data.auth_url
        ) {
          authUrl.value = error.response.data.auth_url;
          errorMessage.value = "";
        } else {
          errorMessage.value =
            error.response?.data?.detail ||
            error.message ||
            "Failed to load emails.";
        }
      } finally {
        loading.value = false;
      }
    };

    const authenticate = () => {
      if (authUrl.value) {
        sessionStorage.setItem("oauth_redirect_path", window.location.pathname);
        window.location.href = authUrl.value;
      } else {
        errorMessage.value =
          "Authentication URL is missing. Please try reloading the page.";
      }
    };

    // ⭐ FAVORITE / UNFAVORITE TOGGLE
    const handleFavorite = async (email) => {
      if (!email || !email.message_id) return;
      if (isTrash.value) return; // safety: no starring in Trash

      const newValue = !email.isStarred;

      try {
        // setEmailStar should send a raw boolean body (true/false)
        await setEmailStar(email.message_id, newValue);

        // Optimistic UI update
        email.isStarred = newValue;

        // If we’re in Favorites view and user unstars → remove from list
        const isFavoritesFolder =
          props.folder === "favorites" || props.folder === "starred";

        if (!newValue && isFavoritesFolder) {
          emails.value = emails.value.filter(
            (e) => e.message_id !== email.message_id
          );

          if (
            selectedEmail.value &&
            selectedEmail.value.message_id === email.message_id
          ) {
            selectedEmail.value = null;
          }
        }
      } catch (error) {
        console.error("Failed to update favorite:", error);
        errorMessage.value =
          error.response?.data?.detail ||
          error.message ||
          "Failed to update favorite.";
      }
    };

    const handleDelete = async () => {
      if (!selectedEmail.value) return;

      try {
        const messageId = selectedEmail.value.message_id;

        await deleteEmail(messageId);

        emails.value = emails.value.filter(
          (email) => email.message_id !== messageId
        );

        selectedEmail.value = null;
      } catch (error) {
        console.error("Failed to delete email:", error);
        errorMessage.value =
          error.response?.data?.detail ||
          error.message ||
          "Failed to delete email.";
      }
    };

    const handleRestore = async (email) => {
      try {
        const messageId = email.message_id;
        await restoreEmail(messageId);

        emails.value = emails.value.filter((e) => e.message_id !== messageId);

        if (
          selectedEmail.value &&
          selectedEmail.value.message_id === messageId
        ) {
          selectedEmail.value = null;
        }
      } catch (error) {
        console.error("Failed to restore email:", error);
        errorMessage.value =
          error.response?.data?.detail ||
          error.message ||
          "Failed to restore email.";
      }
    };

    onMounted(() => {
      loadEmails();
    });

    watch(
      () => props.folder,
      () => {
        loadEmails();
      }
    );

    watch(
      () => route.query.label,
      () => {
        if (props.folder === "inbox") {
          loadEmails();
        }
      }
    );

    // Watch for account selection changes
    watch(
      () => props.selectedAccountId,
      () => {
        if (props.folder === "inbox") {
          loadEmails();
        }
      }
    );

    const selectEmail = (email) => {
      selectedEmail.value = email;
    };

    const closeEmail = () => {
      selectedEmail.value = null;
    };

    const formatDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      const today = new Date();
      if (date.toDateString() === today.toDateString()) {
        return date.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
      }
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);
      if (date.toDateString() === yesterday.toDateString()) {
        return "Yesterday";
      }
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    };

    const formatFullDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleString([], {
        weekday: "short",
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    };

    const getPreview = (body) => {
      if (!body) return "";
      const plainText = body.replace(/<[^>]*>/g, "");
      return (
        plainText.substring(0, 100) + (plainText.length > 100 ? "..." : "")
      );
    };

    const sanitizeHtml = (html) => {
      if (!html) return "";
      return html;
    };

    const getLabelText = (prediction) => {
      const labels = {
        'spam': 'Spam',
        'ham': 'Normal',
        'important': 'Important'
      };
      return labels[prediction] || prediction;
    };

    const openLabelMenu = async () => {
      if (!selectedEmail.value) return;

      showLabelMenu.value = true;
      labelMenuError.value = "";
      labelMenuLoading.value = true;

      try {
        if (!availableLabels.value.length) {
          const data = await fetchLabels();
          availableLabels.value = Array.isArray(data) ? data : [];
        }
        // Initialize checked labels from the selected email
        selectedLabelIds.value = [...(selectedEmail.value.label_ids || [])];
      } catch (e) {
        console.error("Failed to load labels:", e);
        labelMenuError.value =
          e?.response?.data?.detail || e?.message || "Failed to load labels.";
      } finally {
        labelMenuLoading.value = false;
      }
    };

    const closeLabelMenu = () => {
      if (savingLabels.value) return;
      showLabelMenu.value = false;
    };

    const toggleLabelMenu = async () => {
      if (showLabelMenu.value) {
        // if already open, close it
        closeLabelMenu();
        return;
      }
      // if closed, open and load labels
      await openLabelMenu();
    };

    const saveLabelChanges = async () => {
      if (!selectedEmail.value) return;
      if (!availableLabels.value.length) {
        showLabelMenu.value = false;
        return;
      }

      const current = new Set(selectedEmail.value.label_ids || []);
      const next = new Set(selectedLabelIds.value || []);

      const add = [];
      const remove = [];

      // Figure out what changed
      availableLabels.value.forEach((lab) => {
        const hadBefore = current.has(lab.id);
        const hasNow = next.has(lab.id);

        if (hasNow && !hadBefore) add.push(lab.id);
        if (!hasNow && hadBefore) remove.push(lab.id);
      });

      // Nothing changed? Close.
      if (!add.length && !remove.length) {
        showLabelMenu.value = false;
        return;
      }

      savingLabels.value = true;
      labelMenuError.value = "";

      try {
        await updateEmailLabels(selectedEmail.value.message_id, {
          addLabelIds: add,
          removeLabelIds: remove,
        });

        // Update local label_ids for selected email
        const newLabelIds = Array.from(
          new Set([...current, ...add].filter((id) => !remove.includes(id)))
        );

        // 🔹 Update selected email object
        selectedEmail.value = {
          ...selectedEmail.value,
          label_ids: newLabelIds,
        };

        // 🔹 Update email in the list
        emails.value = emails.value.map((e) =>
          e.message_id === selectedEmail.value.message_id
            ? { ...e, label_ids: newLabelIds }
            : e
        );

        // 🔹 If we are in a label view and this email no longer has that label,
        //     remove it from the current list (Gmail behavior)
        const currentLabelId = activeLabelId.value;
        if (currentLabelId && !newLabelIds.includes(currentLabelId)) {
          emails.value = emails.value.filter(
            (e) => e.message_id !== selectedEmail.value.message_id
          );
          selectedEmail.value = null;
        }

        showLabelMenu.value = false;
      } catch (e) {
        console.error("Failed to update labels for this email:", e);
        labelMenuError.value =
          e?.response?.data?.detail || e?.message || "Failed to update labels.";
      } finally {
        savingLabels.value = false;
      }
    };

    return {
      emails,
      loading,
      errorMessage,
      selectedEmail,
      authUrl,
      selectEmail,
      closeEmail,
      handleFavorite,
      handleDelete,
      handleRestore,
      isTrash,
      formatDate,
      formatFullDate,
      getPreview,
      getLabelText,
      sanitizeHtml,
      loadEmails,
      authenticate,
      // Label menu
      showLabelMenu,
      availableLabels,
      labelMenuLoading,
      labelMenuError,
      selectedLabelIds,
      savingLabels,
      openLabelMenu,
      closeLabelMenu,
      saveLabelChanges,
      toggleLabelMenu,
    };
  },
};
</script>

<style scoped>
/* Standard Loading & Error Styles */
.loading,
.no-emails {
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.error-box {
  background-color: #fffbeb;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  padding: 1.5rem;
  margin: 1rem 0;
}

.auth-prompt {
  background-color: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 6px;
  padding: 2rem;
  margin: 1rem 0;
  text-align: center;
}

.auth-prompt h2 {
  color: #0050b3;
  margin-bottom: 0.5rem;
}
.auth-prompt p {
  color: #0050b3;
}

.btn-primary {
  background-color: #4285f4;
  color: white;
  border: none;
  padding: 12px 25px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 1rem;
  margin-top: 1rem;
  transition: background-color 0.2s;
}
.btn-primary:hover {
  background-color: #337ae2;
}

.error-box h3 {
  margin-top: 0;
  color: #d46b08;
  font-weight: 700;
}
.error-box p {
  color: #d48806;
}
.setup-instructions {
  margin-top: 1rem;
  padding: 1rem;
  background-color: #fff;
  border-radius: 4px;
  border: 1px solid var(--light-border-color);
}
.setup-instructions ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

/* Email Container */
.email-container {
  display: flex;
  height: calc(100vh - 200px);
  gap: 0;
  overflow: hidden;
}

.email-list-panel {
  flex: 0 0 400px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border-color, #e0e0e0);
  overflow: hidden;
}

.email-list-panel.full-width {
  flex: 1;
  border-right: none;
}

/* IMPORTANT: This ensures the list scrolls if there are too many items */
.email-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.email-detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--content-bg, #ffffff);
}

/* Email Item Styles */
.email-item {
  background-color: var(--read-email-bg, #f7f8fa);
  border: none;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  padding: 1rem 1.25rem;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: none;
  border-left: 4px solid transparent;
  position: relative; /* 🔹 needed for bottom-right restore */
  padding-right: 4.5rem; /* 🔹 leave space for restore button */
  padding-bottom: 1.75rem; /* 🔹 so preview doesn’t overlap button */
}

.email-item.unread {
  background-color: var(--content-bg, #ffffff);
}

.email-item:last-child {
  border-bottom: none;
}

.email-item:not(.selected):hover {
  background-color: var(--hover-bg, #f0f4f8);
}

.email-item.selected {
  background-color: var(--hover-bg, #f0f4f8);
  border-left: 4px solid var(--primary-color, #6c63ff);
}

.email-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

/* Flexbox wrapper for sender + ML label */
.sender-with-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.email-sender {
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 1.05rem;
}

/* Account Badge */
.account-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 500;
  white-space: nowrap;
  flex-shrink: 0;
  background-color: #e3f2fd;
  color: #1565c0;
  border: 1px solid #bbdefb;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ML Classification Label Badges */
.ml-label {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  white-space: nowrap;
  flex-shrink: 0;
}

.ml-label-spam {
  background-color: #fee;
  color: #c33;
  border: 1px solid #fcc;
}

.ml-label-important {
  background-color: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.ml-label-ham {
  background-color: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.email-subject {
  font-weight: 500;
  font-size: 1rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-date {
  font-size: 0.8rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.email-preview {
  font-size: 0.9rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-item.unread .email-sender,
.email-item.unread .email-subject {
  font-weight: 700;
  color: var(--text-primary, #333);
}

.email-item:not(.selected):hover {
  background-color: var(--hover-bg, #f0f4f8);
  cursor: pointer;
  border-left: 4px solid rgba(108, 99, 255, 0.3);
}

/* REMOVED: All .pagination related styles */

/* Email Detail Styles */
.email-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
  background-color: var(--content-bg, #ffffff);
}

.email-actions {
  display: flex;
  gap: 0.5rem;
}

/* Unified Button Style for Material Icons */
.icon-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px; /* Fixed width for square shape */
  height: 40px; /* Fixed height */
  padding: 0;
  border: 1px solid var(--border-color, #e0e0e0);
  background-color: var(--content-bg, #ffffff);
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary, #666);
  transition: all 0.2s ease;
}

.icon-action-btn:hover {
  background-color: var(--hover-bg, #f0f4f8);
  color: var(--text-primary, #333);
  border-color: #d0d0d0;
}

/* Material Symbol Font Size Settings */
.material-symbols-outlined {
  font-size: 20px;
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
}

.email-detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
}

.email-detail-subject {
  font-size: 1.5rem;
  margin: 0 0 1.5rem 0;
  color: var(--text-primary, #333);
}

.email-detail-meta {
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.sender-info {
  display: flex;
  align-items: center;
}

.sender-details {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sender-name {
  font-weight: 600;
  color: var(--text-primary, #333);
  font-size: 1.1rem;
}

.email-date-full {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.account-info {
  margin-top: 0.5rem;
}

.email-body {
  line-height: 1.6;
  color: var(--text-primary, #333);
  white-space: normal; /* allow wrapping */
  word-break: break-word; /* long URLs won’t overflow */
  font-size: 0.95rem;
}
.email-body a {
  text-decoration: underline;
  cursor: pointer;
}

/* 🔹 Bottom-right restore button */
.restore-btn {
  position: absolute;
  bottom: 0.75rem;
  right: 0.75rem;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, background-color 0.2s ease, color 0.2s ease,
    border-color 0.2s ease;
}

/* Show restore button when the row is hovered (desktop) */
.email-item:hover .restore-btn {
  opacity: 1;
  pointer-events: auto;
}

/* Hover: turn blue with white icon */
.restore-btn:hover {
  background-color: #6c63ff;
  border-color: #6c63ff;
  color: #ffffff;
}

.restore-btn:hover .material-symbols-outlined {
  color: #ffffff;
}

/* Star icon in detail header */
.star-toggle {
  font-size: 22px;
  transition: color 0.15s ease, font-variation-settings 0.15s ease;
}

/* NOT STARRED — outlined gray like other icons */
.star-normal {
  color: var(--text-secondary, #666);
  font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
}

/* STARRED — filled in app primary color */
.star-filled {
  color: #6c63ff;
  font-variation-settings: "FILL" 1, "wght" 400, "GRAD" 0, "opsz" 24;
}

.label-menu-wrapper {
  position: relative;
}

/* Small dropdown under the label button */
.label-menu-popover {
  position: absolute;
  top: 110%;
  right: 0;
  background: #ffffff;
  border-radius: 10px;
  width: 260px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
  border: 1px solid rgba(148, 163, 184, 0.4);
  padding: 0.75rem 0.9rem 0.8rem;
  z-index: 20;
  font-size: 0.9rem;
}

.label-menu-title {
  margin: 0 0 0.4rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.label-menu-status,
.label-menu-empty {
  font-size: 0.82rem;
  color: var(--text-secondary, #6b7280);
}

.label-menu-error {
  font-size: 0.82rem;
  color: var(--danger-color, #e53935);
  margin-bottom: 0.4rem;
}

/* List */
.label-menu-list {
  list-style: none;
  margin: 0.2rem 0 0.6rem;
  padding: 0;
  max-height: 180px;
  overflow-y: auto;
}

.label-menu-row + .label-menu-row {
  margin-top: 0.15rem;
}

.label-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.25rem 0.1rem;
  border-radius: 4px;
  cursor: pointer;
}

.label-checkbox-row:hover {
  background-color: rgba(148, 163, 184, 0.15);
}

.label-checkbox-row input[type="checkbox"] {
  width: 14px;
  height: 14px;
}

.label-name {
  flex: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

/* Footer buttons */
.label-menu-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.3rem;
}

.label-btn {
  font-size: 0.85rem;
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  border: 1px solid transparent;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease,
    border-color 0.15s ease, box-shadow 0.15s ease;
}

.label-btn:disabled {
  opacity: 0.6;
  cursor: default;
}

/* Cancel = subtle text button */
.label-btn-cancel {
  background-color: transparent;
  color: var(--text-secondary, #6b7280);
  border-color: transparent;
}

.label-btn-cancel:hover:not(:disabled) {
  background-color: rgba(148, 163, 184, 0.12);
}

/* Apply = primary pill button */
.label-btn-apply {
  background-color: #2563eb;
  color: #ffffff;
  border-color: #2563eb;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.25);
}

.label-btn-apply:hover:not(:disabled) {
  background-color: #1d4ed8;
  border-color: #1d4ed8;
}

/* Mobile Responsive */
@media (max-width: 768px) {
  .email-container {
    display: flex;
    height: calc(100vh - 100px);
    gap: 0;
    overflow: hidden;
  }

  .email-list-panel {
    flex: 0 0 auto;
    border-right: none;
    border-bottom: 1px solid var(--border-color, #e0e0e0);
    max-height: none;
  }

  .email-list-panel.full-width {
    flex: 1;
  }

  .email-list-panel.hide-on-mobile {
    display: none;
  }

  .email-detail-panel {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 100;
  }

  /* 🔹 On mobile: keep restore button visible and inline (no absolute) */
  .restore-btn {
    position: static;
    opacity: 1;
    pointer-events: auto;
    margin-top: 0.5rem;
    align-self: flex-start;
  }
}
</style>
