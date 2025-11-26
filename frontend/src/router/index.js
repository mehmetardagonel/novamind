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
      // 1. Inbox
      {
        path: 'email/inbox', 
        name: 'EmailInbox',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/EmailView.vue'),
        props: { folder: 'inbox' } 
      },
      // 2. Sent
      {
        path: 'email/sent', 
        name: 'EmailSent',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/SentView.vue'),
        props: true 
      },
      // 3. Favorites
      {
        path: 'email/favorites', 
        name: 'EmailFavorites',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/FavoritesView.vue'),
        props: true 
      },
      // --- NEW: Important ---
      {
        path: 'email/important', 
        name: 'EmailImportant',
        // Assuming you create ImportantView.vue, otherwise point to EmailView.vue
        component: () => import(/* webpackChunkName: "email-view" */ '../views/ImportantView.vue'),
        props: true 
      },
      // --- NEW: Spam ---
      {
        path: 'email/spam', 
        name: 'EmailSpam',
        // Assuming you create SpamView.vue
        component: () => import(/* webpackChunkName: "email-view" */ '../views/SpamView.vue'),
        props: true 
      },
      // 4. Drafts
      {
        path: 'email/drafts', 
        name: 'EmailDrafts',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/DraftsView.vue'),
        props: true 
      },
      // 5. Trash
      {
        path: 'email/trash', 
        name: 'EmailTrash',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/TrashView.vue'),
        props: true 
      },
      // --- NEW: Labels ---
      {
        path: 'email/labels', 
        name: 'EmailLabels',
        // Assuming you create LabelsView.vue
        component: () => import(/* webpackChunkName: "email-view" */ '../views/LabelsView.vue'),
        props: true 
      },
      // 6. Compose Route
      {
        path: 'compose',
        name: 'Compose',
        component: () => import(/* webpackChunkName: "compose-view" */ '../views/ComposeView.vue')
      },
      // 7. Redirect Default
      {
        path: '',
        redirect: '/app/email/inbox' 
      }
    ]
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router