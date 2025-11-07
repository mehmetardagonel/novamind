<template>
  <div>
    <router-view />
  </div>
</template>

<script>
// We no longer need to import LoginScreen or MainApp here
// The router handles this based on the current path.
// The ref and function are also no longer needed.
import { onMounted } from 'vue'
import router from './router/index.js' // We might need to import the router for initial navigation

export default {
  // components: { LoginScreen, MainApp }, // <-- REMOVED

  setup() {
    // Check if the user is trying to access the root path, and redirect them
    // The redirect logic in router/index.js will handle the initial path.

    // If the component is intended only for routing, the setup can be simplified
    // or entirely removed if no local state is needed.

    // Optional: Redirect / to /login if it's the very first load and no path is specified
    onMounted(() => {
      if (router.currentRoute.value.path === '/') {
        router.push('/login')
      }
    })


    return {} // Return nothing if there's no reactive state or methods
  },
}
</script>