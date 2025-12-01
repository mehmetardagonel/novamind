<template>
  <div class="main-content-wrapper">
    <EmailListView folder="sent" key="sent" />
  </div>
</template>

<script>
import EmailListView from '../components/EmailListView.vue'

export default {
  name: 'SentView',
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
