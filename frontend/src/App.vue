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

<style>

html, body {
  /* 1. Remove default outer spacing */
  margin: 0;
  padding: 0;
  
  /* 2. Ensure the body takes up the full browser height */
  height: 100%; 
  width: 100%;
}

/* Ensure the root element of your Vue app is also full height */
#app {
  height: 100%;
  width: 100%;
}</style>