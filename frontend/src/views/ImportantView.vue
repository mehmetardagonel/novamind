<template>
  <div class="main-content-wrapper">
    <EmailListView folder="important" key="important" />
  </div>
</template>

<script>
import EmailListView from '../components/EmailListView.vue'

export default {
  name: 'ImportantView',
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
