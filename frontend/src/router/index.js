// src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import(/* webpackChunkName: "home" */ '../components/LandingPage.vue')
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import(/* webpackChunkName: "login" */ '../components/LoginScreen.vue')
  },
  {
    path: '/app',
    name: 'App',
    component: () => import(/* webpackChunkName: "main" */ '../components/MainApp.vue')
  },
  {
    path: '/signup',
    name: 'SignUp',
    component: () => import(/* webpackChunkName: "signup" */ '../components/SignUpScreen.vue')
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router // <--- Must be exported!