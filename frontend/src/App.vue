<template>
  <div>
    <router-view />
  </div>
</template>

<script>
import { onMounted } from 'vue'
import router from './router/index.js' // We might need to import the router for initial navigation

export default {

  setup() {
    // Optional: Redirect / to /login if it's the very first load and no path is specified
    onMounted(() => {
      if (router.currentRoute.value.path === '/') {
        router.push('/home')
      }
    })


    return {} // Return nothing if there's no reactive state or methods
  },
}
</script>

