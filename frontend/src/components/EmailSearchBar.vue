<template>
  <div class="email-search-bar">
    <div class="search-input-wrapper">
      <span class="material-symbols-outlined search-icon">search</span>
      <input
        type="text"
        class="search-input"
        v-model="searchQuery"
        @keyup.enter="handleSearch"
        :placeholder="placeholder"
      />
      <button
        v-if="searchQuery"
        class="clear-btn"
        @click="handleClear"
        title="Clear search"
      >
        <span class="material-symbols-outlined">close</span>
      </button>
      <button
        class="search-btn"
        @click="handleSearch"
        :disabled="!searchQuery.trim()"
        title="Search"
      >
        Search
      </button>
    </div>

    <div v-if="showAdvanced" class="advanced-search-panel">
      <div class="advanced-search-header">
        <h3>Advanced Search</h3>
        <button class="close-advanced-btn" @click="toggleAdvanced">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <div class="advanced-search-fields">
        <div class="field-group">
          <label>From</label>
          <input
            type="text"
            v-model="advancedFilters.from"
            placeholder="sender@example.com"
          />
        </div>

        <div class="field-group">
          <label>To</label>
          <input
            type="text"
            v-model="advancedFilters.to"
            placeholder="recipient@example.com"
          />
        </div>

        <div class="field-group">
          <label>Subject</label>
          <input
            type="text"
            v-model="advancedFilters.subject"
            placeholder="Subject keywords"
          />
        </div>

        <div class="field-group">
          <label>Keywords</label>
          <input
            type="text"
            v-model="advancedFilters.keywords"
            placeholder="Search in email body"
          />
        </div>

        <div class="field-row">
          <div class="field-group">
            <label>After</label>
            <input
              type="date"
              v-model="advancedFilters.after"
            />
          </div>

          <div class="field-group">
            <label>Before</label>
            <input
              type="date"
              v-model="advancedFilters.before"
            />
          </div>
        </div>

        <div class="field-group">
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="advancedFilters.unread"
            />
            <span>Unread only</span>
          </label>
          <label class="checkbox-label">
            <input
              type="checkbox"
              v-model="advancedFilters.hasAttachment"
            />
            <span>Has attachment</span>
          </label>
        </div>
      </div>

      <div class="advanced-search-footer">
        <button class="btn-secondary" @click="resetAdvanced">Reset</button>
        <button class="btn-primary" @click="applyAdvanced">Apply Filters</button>
      </div>
    </div>

    <div class="search-hints">
      <button class="hint-toggle" @click="toggleAdvanced">
        <span class="material-symbols-outlined">
          {{ showAdvanced ? 'expand_less' : 'expand_more' }}
        </span>
        {{ showAdvanced ? 'Hide' : 'Show' }} advanced search
      </button>
      <div v-if="!showAdvanced" class="quick-hints">
        <span class="hint-label">Quick tips:</span>
        <code>from:google</code>
        <code>subject:meeting</code>
        <code>is:unread</code>
        <code>has:attachment</code>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue';

export default {
  name: 'EmailSearchBar',
  props: {
    placeholder: {
      type: String,
      default: 'Search emails (e.g., from:google subject:jobs is:unread)'
    }
  },
  emits: ['search', 'clear'],
  setup(props, { emit }) {
    const searchQuery = ref('');
    const showAdvanced = ref(false);

    const advancedFilters = ref({
      from: '',
      to: '',
      subject: '',
      keywords: '',
      after: '',
      before: '',
      unread: false,
      hasAttachment: false
    });

    const toggleAdvanced = () => {
      showAdvanced.value = !showAdvanced.value;
    };

    const buildQueryFromAdvanced = () => {
      const parts = [];

      if (advancedFilters.value.from) {
        parts.push(`from:${advancedFilters.value.from}`);
      }
      if (advancedFilters.value.to) {
        parts.push(`to:${advancedFilters.value.to}`);
      }
      if (advancedFilters.value.subject) {
        parts.push(`subject:${advancedFilters.value.subject}`);
      }
      if (advancedFilters.value.keywords) {
        parts.push(advancedFilters.value.keywords);
      }
      if (advancedFilters.value.after) {
        const formattedDate = advancedFilters.value.after.replace(/-/g, '/');
        parts.push(`after:${formattedDate}`);
      }
      if (advancedFilters.value.before) {
        const formattedDate = advancedFilters.value.before.replace(/-/g, '/');
        parts.push(`before:${formattedDate}`);
      }
      if (advancedFilters.value.unread) {
        parts.push('is:unread');
      }
      if (advancedFilters.value.hasAttachment) {
        parts.push('has:attachment');
      }

      return parts.join(' ');
    };

    const handleSearch = () => {
      const query = searchQuery.value.trim();
      if (query) {
        emit('search', query);
      }
    };

    const handleClear = () => {
      searchQuery.value = '';
      emit('clear');
    };

    const applyAdvanced = () => {
      const query = buildQueryFromAdvanced();
      if (query) {
        searchQuery.value = query;
        emit('search', query);
        showAdvanced.value = false;
      }
    };

    const resetAdvanced = () => {
      advancedFilters.value = {
        from: '',
        to: '',
        subject: '',
        keywords: '',
        after: '',
        before: '',
        unread: false,
        hasAttachment: false
      };
    };

    return {
      searchQuery,
      showAdvanced,
      advancedFilters,
      toggleAdvanced,
      handleSearch,
      handleClear,
      applyAdvanced,
      resetAdvanced,
      buildQueryFromAdvanced
    };
  }
};
</script>

<style scoped>
.email-search-bar {
  padding: 1rem;
  background-color: var(--content-bg, #ffffff);
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
  background-color: var(--content-bg, #ffffff);
  transition: border-color 0.2s ease;
}

.search-input-wrapper:focus-within {
  border-color: var(--primary-color, #6c63ff);
  box-shadow: 0 0 0 2px rgba(108, 99, 255, 0.1);
}

.search-icon {
  color: var(--text-secondary, #666);
  font-size: 20px;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 0.95rem;
  color: var(--text-primary, #333);
  background-color: transparent;
}

.search-input::placeholder {
  color: var(--text-secondary, #999);
}

.clear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background-color: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--text-secondary, #666);
  transition: background-color 0.2s ease, color 0.2s ease;
}

.clear-btn:hover {
  background-color: var(--hover-bg, #f0f4f8);
  color: var(--text-primary, #333);
}

.clear-btn .material-symbols-outlined {
  font-size: 18px;
}

.search-btn {
  padding: 0.5rem 1rem;
  background-color: var(--primary-color, #6c63ff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background-color 0.2s ease, opacity 0.2s ease;
}

.search-btn:hover:not(:disabled) {
  background-color: #5a52e8;
}

.search-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.search-hints {
  margin-top: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.hint-toggle {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.35rem 0.75rem;
  background-color: transparent;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  color: var(--text-secondary, #666);
  transition: all 0.2s ease;
}

.hint-toggle:hover {
  background-color: var(--hover-bg, #f0f4f8);
  color: var(--text-primary, #333);
}

.hint-toggle .material-symbols-outlined {
  font-size: 18px;
}

.quick-hints {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.hint-label {
  font-size: 0.85rem;
  color: var(--text-secondary, #666);
}

.quick-hints code {
  padding: 0.25rem 0.5rem;
  background-color: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 0.8rem;
  color: #333;
  font-family: 'Monaco', 'Courier New', monospace;
}

.advanced-search-panel {
  margin-top: 1rem;
  padding: 1rem;
  background-color: var(--hover-bg, #f9fafb);
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 8px;
}

.advanced-search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.advanced-search-header h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--text-primary, #333);
  font-weight: 600;
}

.close-advanced-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background-color: transparent;
  border-radius: 50%;
  cursor: pointer;
  color: var(--text-secondary, #666);
  transition: all 0.2s ease;
}

.close-advanced-btn:hover {
  background-color: var(--content-bg, #ffffff);
  color: var(--text-primary, #333);
}

.advanced-search-fields {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field-group label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary, #333);
}

.field-group input[type="text"],
.field-group input[type="date"] {
  padding: 0.5rem;
  border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px;
  font-size: 0.9rem;
  color: var(--text-primary, #333);
  background-color: var(--content-bg, #ffffff);
  transition: border-color 0.2s ease;
}

.field-group input:focus {
  outline: none;
  border-color: var(--primary-color, #6c63ff);
  box-shadow: 0 0 0 2px rgba(108, 99, 255, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--text-primary, #333);
}

.checkbox-label input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--primary-color, #6c63ff);
}

.advanced-search-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-color, #e0e0e0);
}

.btn-primary,
.btn-secondary {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background-color: var(--primary-color, #6c63ff);
  color: white;
  border: none;
}

.btn-primary:hover {
  background-color: #5a52e8;
}

.btn-secondary {
  background-color: transparent;
  color: var(--text-secondary, #666);
  border: 1px solid var(--border-color, #e0e0e0);
}

.btn-secondary:hover {
  background-color: var(--hover-bg, #f0f4f8);
  color: var(--text-primary, #333);
}

@media (max-width: 768px) {
  .search-input-wrapper {
    flex-wrap: wrap;
  }

  .search-btn {
    width: 100%;
  }

  .quick-hints {
    display: none;
  }

  .field-row {
    grid-template-columns: 1fr;
  }
}
</style>
