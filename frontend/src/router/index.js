
// src/router/index.js

import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'   // 👈 NEW

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

  // --- /app layout with children ---
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
      // Important
      {
        path: 'email/important',
        name: 'EmailImportant',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/ImportantView.vue'),
        props: true
      },
      // Spam
      {
        path: 'email/spam',
        name: 'EmailSpam',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/SpamView.vue'),
        props: true
      },
      // Drafts
      {
        path: 'email/drafts',
        name: 'EmailDrafts',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/DraftsView.vue'),
        props: true
      },
      // Trash
      {
        path: 'email/trash',
        name: 'EmailTrash',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/TrashView.vue'),
        props: true
      },
      // Labels
      {
        path: 'email/labels',
        name: 'EmailLabels',
        component: () => import(/* webpackChunkName: "email-view" */ '../views/LabelsView.vue'),
        props: true
      },
      // Compose
      {
        path: 'compose',
        name: 'Compose',
        component: () => import(/* webpackChunkName: "compose-view" */ '../views/ComposeView.vue')
      },
      // Accounts Management
      {
        path: 'accounts',
        name: 'Accounts',
        component: () => import(/* webpackChunkName: "accounts-view" */ '../views/AccountsView.vue')
      },
      // Default child route -> inbox
      {
        path: '',
        name: 'Default',
        redirect: '/app/email/inbox'
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

/**
 * GLOBAL AUTH GUARD
 * - If logged in and hits / or /home -> redirect to /app/email/inbox
 * - Protect /app routes from unauthenticated users -> /login
 * - If already logged in and hits /login -> go to inbox
 */
let authInitialized = false

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Ensure Supabase session is restored once on app start
  if (!authInitialized && authStore.refreshUser) {
    await authStore.refreshUser()
    authInitialized = true
  }

  const isAuthed = authStore.isAuthenticated

  // If user is logged in and goes to / or /home, send them to inbox
  if ((to.path === '/' || to.path === '/home') && isAuthed) {
    return next('/app/email/inbox')
  }

  // If user is logged in and tries to access login again, also send them to inbox
  if (to.path === '/login' && isAuthed) {
    return next('/app/email/inbox')
  }

  // Protect /app routes for unauthenticated users
  if (to.path.startsWith('/app') && !isAuthed) {
    return next('/login')
  }

  return next()
})

export default router
