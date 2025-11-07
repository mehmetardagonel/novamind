// src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // Your other routes go here
  {
    path: '/login', // Make sure you have a route for /login
    name: 'Login',
    component: () => import(/* webpackChunkName: "login" */ '../components/LoginScreen.vue')
  },
  {
    path: '/App', // Your MainApp path
    name: 'App',
    component: () => import(/* webpackChunkName: "main" */ '../components/MainApp.vue')
  },
  {
    path: '/signup', // Your MainApp path
    name: 'SignUp',
    component: () => import(/* webpackChunkName: "main" */ '../components/SignUpScreen.vue')
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router // <--- Must be exported!