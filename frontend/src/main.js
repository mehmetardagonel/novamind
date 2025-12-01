// main.js (Your main entry file)

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './global.css'  

const app = createApp(App)
app.config.devtools = false
const pinia = createPinia()

app.use(pinia)
app.use(router)

app.mount('#app')
