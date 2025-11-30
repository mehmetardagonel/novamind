<template>
  <div class="main-content-wrapper">
    <EmailListView folder="drafts" key="drafts" />
  </div>
</template>

<script>
import EmailListView from '../components/EmailListView.vue'

export default {
  name: 'DraftsView',
  components: { EmailListView }
}
</script>

<style scoped>
.main-content-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
