<template>
  <div class="main-content-wrapper">
    <EmailListView folder="trash" key="trash" />
  </div>
</template>

<script>
import EmailListView from "../components/EmailListView.vue";

export default {
  name: "TrashView",
  components: { EmailListView },
};
</script>

<style scoped>
.main-content-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}
</style>
