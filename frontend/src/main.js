// main.js (Your main entry file)

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './global.css'
import { SplashScreen } from '@capacitor/splash-screen'

const app = createApp(App)
app.config.devtools = false
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.mount('#app')

// Hide splash screen when app is ready
SplashScreen.hide()
