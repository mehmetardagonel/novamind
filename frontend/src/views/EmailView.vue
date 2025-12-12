<template>
  <div class="main-content-wrapper">
    <EmailListView
      :folder="folder"
      :selected-account-id="selectedAccountId"
      :key="folder"
    />
  </div>
</template>

<script>
import EmailListView from '../components/EmailListView.vue';
import { computed } from 'vue';

export default {
  name: 'EmailView',
  components: {
    EmailListView,
  },
  props: {
    folder: {
        type: String,
        required: true,
        default: 'inbox'
    },
    selectedAccountId: {
        type: String,
        default: null
    }
  },
  setup(props) {
    // Determine the current folder based on the prop
    const folder = computed(() => props.folder);


    return {
      folder
    }
  }
};
</script>

<style scoped>
.main-content-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>