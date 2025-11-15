<template>
  <div class="main-content-wrapper">
    <EmailListView :folder="folder" :key="folder" />
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
    }
  },
  setup(props) {
    // Determine the current folder based on the prop
    const folder = computed(() => props.folder);

    // REMOVED: folderName computed property is no longer needed

    return {
      folder
      // REMOVED: folderName
    }
  }
};
</script>

<style scoped>
/* REMOVED: All styles related to H2 are gone */
.main-content-wrapper {
  /* You might want to add padding here if the parent doesn't have it */
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>