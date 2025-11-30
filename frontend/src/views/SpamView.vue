<template>
  <div class="main-content-wrapper">
    <EmailListView folder="spam" key="spam" />
  </div>
</template>

<script>
import EmailListView from '../components/EmailListView.vue'

export default {
  name: 'SpamView',
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
