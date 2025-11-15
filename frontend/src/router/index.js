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
    path: '/signup',
    name: 'SignUp',
    component: () => import(/* webpackChunkName: "signup" */ '../components/SignUpScreen.vue')
  },
  // --- Updated /app route for Nested Routing ---
  {
    path: '/app',
    name: 'AppLayout', 
    component: () => import(/* webpackChunkName: "main" */ '../components/MainApp.vue'),
    children: [
      // 1. Explicit Inbox Path: Handles /app/email/inbox
      {
        path: 'email/inbox', 
        name: 'EmailInbox',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/EmailView.vue'),
        // Pass the folder name explicitly as a prop to EmailView
        props: { folder: 'inbox' } 
      },
      {
        path: 'email/sent', 
        name: 'EmailSent',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/SentView.vue'),
        props: true // Passes the 'sent' or 'favorites' parameter as a prop
      },
      {
        path: 'email/favorites', 
        name: 'EmailFavorites',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/FavoritesView.vue'),
        props: true // Passes the 'sent' or 'favorites' parameter as a prop
      },
      {
        path: 'email/drafts', 
        name: 'EmailDrafts',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/DraftsView.vue'),
        props: true // Passes the 'sent' or 'favorites' parameter as a prop
      },
      {
        path: 'email/trash', 
        name: 'EmailTrash',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/TrashView.vue'),
        props: true // Passes the 'sent' or 'favorites' parameter as a prop
      },
      // 3. Compose Route
      {
        path: 'compose',
        name: 'Compose',
        component: () => import(/* webpackChunkName: "compose-view" */ '../views/ComposeView.vue')
      },
      // 4. Redirect: The base /app path now redirects to the explicit inbox path.
      {
        path: '',
        redirect: '/app/email/inbox' // Defaulting to Inbox
      }
    ]
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router // Must be exported!