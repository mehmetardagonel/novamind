<template>
  <div class="labels-view">
    <div v-if="loading" class="labels-skeleton">
      <div v-for="n in 15" :key="n" class="labels-skeleton-row">
        <div class="labels-skel-left">
          <div class="labels-skel-icon shimmer"></div>
          <div class="labels-skel-line shimmer"></div>
        </div>
        <div class="labels-skel-trash shimmer"></div>
      </div>
    </div>

    <div v-else class="labels-content">
      <ul class="labels-list">
        <li v-for="label in labels" :key="label.id" class="label-row">
          <!-- inline delete confirm -->
          <div
            v-if="labelToDelete && labelToDelete.id === label.id"
            class="delete-confirm-row"
          >
            <div class="delete-confirm-text">
              Delete label "{{ label.name }}"?
            </div>
            <div class="delete-confirm-actions">
              <button
                type="button"
                class="btn btn-ghost"
                @click="cancelDelete"
                :disabled="deleting"
              >
                Cancel
              </button>
              <button
                type="button"
                class="btn btn-danger"
                @click="confirmDelete"
                :disabled="deleting"
              >
                Delete
              </button>
            </div>
          </div>

          <!-- normal label row -->
          <div v-else class="label-row-main">
            <button
              class="label-main-btn"
              type="button"
              @click="openLabel(label)"
            >
              <span class="material-symbols-outlined label-icon"> tag </span>
              <span class="label-name">{{ label.name }}</span>
            </button>

            <button
              class="icon-button delete-button"
              type="button"
              title="Delete label"
              @click="requestDelete(label)"
            >
              <span class="material-symbols-outlined"> delete </span>
            </button>
          </div>
        </li>

        <!-- New label row -->
        <li v-if="addingNew" class="label-row new-label-row">
          <div class="new-label-main">
            <span class="material-symbols-outlined label-icon"> tag </span>
            <input
              ref="newLabelInput"
              v-model="newLabelName"
              type="text"
              class="new-label-input"
              placeholder="Label name"
              @keyup.enter="submitNewLabel"
              @keyup.esc="cancelNewLabel"
            />
          </div>

          <div class="new-label-actions">
            <button type="button" class="btn btn-ghost" @click="cancelNewLabel">
              Cancel
            </button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!newLabelName.trim() || saving"
              @click="submitNewLabel"
            >
              {{ saving ? "Creating…" : "Create" }}
            </button>
          </div>
        </li>

        <!-- + New label button -->
        <li v-else class="label-row add-inline-row">
          <button
            type="button"
            class="add-inline-btn"
            @click="startAddingLabel"
          >
            <span class="material-symbols-outlined plus-icon"> add </span>
            <span>New label</span>
          </button>
        </li>
      </ul>

      <p v-if="errorMessage" class="labels-error">
        {{ errorMessage }}
      </p>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { fetchLabels, createLabel, deleteLabel } from "../api/emails";

export default {
  name: "LabelsView",
  setup() {
    const router = useRouter();

    const labels = ref([]);
    const loading = ref(false);
    const saving = ref(false);
    const errorMessage = ref("");

    const addingNew = ref(false);
    const newLabelName = ref("");
    const newLabelInput = ref(null);

    const labelToDelete = ref(null);
    const deleting = ref(false);

    const loadLabels = async () => {
      loading.value = true;
      errorMessage.value = "";

      try {
        const data = await fetchLabels();
        labels.value = Array.isArray(data) ? data : [];
      } catch (err) {
        console.error("Failed to load labels:", err);
        errorMessage.value =
          err?.response?.data?.detail ||
          err?.message ||
          "Failed to load labels.";
      } finally {
        loading.value = false;
      }
    };

    const startAddingLabel = async () => {
      if (addingNew.value) {
        await nextTick();
        if (newLabelInput.value) newLabelInput.value.focus();
        return;
      }

      addingNew.value = true;
      newLabelName.value = "";

      await nextTick();
      if (newLabelInput.value) newLabelInput.value.focus();
    };

    const cancelNewLabel = () => {
      addingNew.value = false;
      newLabelName.value = "";
    };

    const submitNewLabel = async () => {
      const name = newLabelName.value.trim();
      if (!name || saving.value) return;

      saving.value = true;
      errorMessage.value = "";

      try {
        const created = await createLabel(name);
        labels.value.push(created);
        addingNew.value = false;
        newLabelName.value = "";
      } catch (err) {
        console.error("Failed to create label:", err);
        errorMessage.value =
          err?.response?.data?.detail ||
          err?.message ||
          "Failed to create label.";
      } finally {
        saving.value = false;
      }
    };

    const requestDelete = (label) => {
      labelToDelete.value = label;
      errorMessage.value = "";
    };

    const cancelDelete = () => {
      labelToDelete.value = null;
      deleting.value = false;
    };

    const confirmDelete = async () => {
      if (!labelToDelete.value || deleting.value) return;

      deleting.value = true;
      errorMessage.value = "";

      const label = labelToDelete.value;

      try {
        await deleteLabel(label.id);
        labels.value = labels.value.filter((l) => l.id !== label.id);
        labelToDelete.value = null;
      } catch (err) {
        console.error("Failed to delete label:", err);
        errorMessage.value =
          err?.response?.data?.detail ||
          err?.message ||
          "Failed to delete label.";
      } finally {
        deleting.value = false;
      }
    };

    // ✅ Navigate to Inbox view filtered by this label
    const openLabel = (label) => {
      router.push({
        name: "EmailInbox", // this is your inbox route
        query: {
          label: label.id,
          labelName: label.name,
        },
      });
    };

    onMounted(() => {
      loadLabels();
    });

    return {
      labels,
      loading,
      saving,
      errorMessage,
      addingNew,
      newLabelName,
      newLabelInput,
      labelToDelete,
      deleting,
      startAddingLabel,
      cancelNewLabel,
      submitNewLabel,
      requestDelete,
      cancelDelete,
      confirmDelete,
      openLabel,
    };
  },
};
</script>

<style scoped>
.labels-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  box-sizing: border-box;
}

.labels-loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-secondary);
  font-size: 1rem;
}

.labels-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.labels-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.label-row {
  padding: 0.4rem 0.6rem;
  border-radius: 8px;
  transition: background-color 0.15s ease;
}

.label-row:hover {
  background-color: var(--hover-bg);
}

/* normal row layout */
.label-row-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.label-main-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  flex: 1;
  text-align: left;
}

.label-main-btn:focus-visible,
.add-inline-btn:focus-visible {
  outline: 2px solid var(--primary-color, #6c63ff);
  outline-offset: 2px;
}

.label-icon {
  font-size: 18px;
  line-height: 1;
  color: var(--text-secondary);
}

.label-name {
  font-size: 0.95rem;
  color: var(--text-primary);
}

.icon-button {
  border: none;
  background: none;
  cursor: pointer;
  padding: 0.15rem 0.3rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.labels-title {
  font-size: 1.2rem;
  font-weight: 600;
  margin: 0 0 0.75rem;
}

/* Header for Labels / Work */
.label-emails-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.9rem;
}

.labels-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border: none;
  background: none;
  padding: 0.15rem 0.4rem 0.15rem 0;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-secondary, #6b7280);
}

.labels-back-btn .material-symbols-outlined {
  font-size: 18px;
}

.labels-back-btn:hover {
  color: var(--text-primary, #111827);
}

.breadcrumb-separator {
  color: var(--text-secondary, #9ca3af);
  font-size: 0.9rem;
}

.breadcrumb-label-name {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-primary, #111827);
}

/* Emails list */
.label-emails-body {
  margin-top: 0.5rem;
}

.label-emails-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.label-email-row {
  padding: 0.9rem 1rem;
  border-radius: 8px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background-color: #ffffff;
  box-shadow: 0 1px 2px rgba(148, 163, 184, 0.15);
}

.label-email-row + .label-email-row {
  margin-top: 0.5rem;
}

.label-email-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.35rem;
}

.label-email-sender {
  font-weight: 500;
  color: var(--text-primary, #111827);
}

.label-email-date {
  font-size: 0.78rem;
  color: var(--text-secondary, #9ca3af);
}

.label-email-subject {
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
  color: var(--text-primary, #111827);
}

.label-email-snippet {
  font-size: 0.82rem;
  color: var(--text-secondary, #6b7280);
}

.icon-button .material-symbols-outlined {
  font-size: 18px;
}

.icon-button:hover {
  opacity: 0.9;
}

.delete-button {
  color: var(--danger-color, #e53935);
}

/* inline delete confirmation */
.delete-confirm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.3rem 0.4rem;
}

.delete-confirm-text {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.warning-icon {
  font-size: 18px;
  color: var(--danger-color, #e53935);
  margin-top: 0.05rem;
}

.delete-confirm-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.new-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.4rem 0.6rem;
}

.new-label-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.new-label-input {
  background: var(--content-bg);
  border: 1px solid var(--border-color);
  color: var(--text-primary);
}

.new-label-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.8;
}

.new-label-input:focus {
  background: var(--content-bg);
}
.new-label-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
}

.btn {
  border-radius: 6px;
  border: 1px solid transparent;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease,
    color 0.15s ease;
}

.btn-primary {
  background-color: var(--primary-color, #6c63ff);
  color: var(--text-on-primary, #fff);
}

.btn-danger {
  background-color: var(--danger-color, #e53935);
  color: #fff;
}

.btn-primary:disabled,
.btn-danger:disabled {
  opacity: 0.6;
  cursor: default;
}

.btn-ghost {
  background-color: transparent;
  border-color: var(--light-border-color, #ddd);
  color: var(--text-secondary);
}

.btn-ghost:hover {
  background-color: var(--hover-bg);
}

.add-inline-row {
  margin-top: 0.4rem;
}

.add-inline-btn {
  border: none;
  background: none;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--primary-color, #6c63ff);
  padding: 0.25rem 0.4rem;
}

.plus-icon {
  font-size: 20px;
  line-height: 1;
}

.labels-empty {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.labels-error {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  color: var(--danger-color, #e53935);
}

/* Skeleton container – matches list padding and width */
.labels-skeleton {
  margin-top: 0.25rem;
}

/* One skeleton row = one label row */
.labels-skeleton-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem; /* same as .label-row */
  border-radius: 8px;
  min-height: 32px; /* approximate text row height */
}

/* Left side: icon + text */
.labels-skel-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Icon box where the #/tag icon is */
.labels-skel-icon {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  background-color: #e3e3e3;
}

/* Label name line */
.labels-skel-line {
  width: 90px;
  height: 12px;
  border-radius: 4px;
  background-color: #e3e3e3;
}

/* Right delete icon placeholder */
.labels-skel-trash {
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background-color: #e3e3e3;
}

/* Shimmer animation reused */
.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: "";
  position: absolute;
  top: 0;
  left: -150%;
  width: 50%;
  height: 100%;
  background: linear-gradient(
    120deg,
    transparent,
    rgba(255, 255, 255, 0.6),
    transparent
  );
  animation: shimmer 1.2s infinite;
}

@keyframes shimmer {
  0% {
    left: -150%;
  }
  100% {
    left: 150%;
  }
}
</style>
