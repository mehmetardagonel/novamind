<template>
  <div class="app-screen">
    <div
      class="background-image"
      :style="{ backgroundImage: 'url(' + backgroundImageUrl + ')' }"
    ></div>
    <div class="background-overlay"></div>

    <div class="content-wrapper">
      <main class="login-container">
        <div class="login-header">
          <div class="header-logo-wrapper">
            <div class="logo-svg">
              <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"
                  fill="currentColor"
                ></path>
              </svg>
            </div>
            <h1>Novamind.AI</h1>
          </div>
          <p class="header-subtitle">Your Personal AI Email Assistant</p>
        </div>

        <form class="login-form" @submit.prevent="login">
          <div class="input-field-group">
            <label>
              <div class="input-wrapper">
                <input
                  v-model="email"
                  class="form-input"
                  placeholder="Email"
                  type="text"
                  :class="{ 'error-border': emailError }"
                  @keyup.enter="login"
                />
                <span class="email-suffix">@gmail.com</span>
              </div>
              <p v-if="emailError" class="error-input">{{ emailError }}</p>
            </label>
          </div>

          <div class="input-field-group">
            <label>
              <div class="input-wrapper">
                <input
                  v-model="password"
                  class="form-input"
                  placeholder="Password"
                  :class="{ 'error-border': passwordError }"
                  :type="passwordVisible ? 'text' : 'password'"
                  @keyup.enter="login"
                />
                <button
                  aria-label="Toggle password visibility"
                  class="password-toggle"
                  type="button"
                  @click.prevent="togglePasswordVisibility"
                >
                  <span class="material-symbols-outlined">
                    {{ passwordVisible ? 'Hide' : 'Show' }}
                  </span>
                </button>
              </div>
              <p v-if="passwordError" class="error-input">{{ passwordError }}</p>
            </label>
          </div>
          <a class="forgot-password-link" href="#">Forgot Password?</a>
          <button 
            @click="login" 
            class="primary-button" 
            :disabled="loading"
            type="submit"
          >
            {{ loading ? 'Logging In...' : 'Log In' }}
          </button>
        </form>

        <div class="signup-link-wrapper">
          <p>
            Don't have an account? 
            <a @click="goToSignup" class="link-button" href="#">Sign Up</a>
          </p>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import BackgroundImage from '@/assets/background.png';
import { supabase } from '@/database/supabaseClient';

export default {
  data() {
    return {
      backgroundImageUrl: BackgroundImage, // Added background image path
      email: '',
      password: '',
      emailError: '',
      passwordError: '',
      passwordVisible: false,
      loading: false, 
    }
  },
  methods: {

    togglePasswordVisibility() {
      this.passwordVisible = !this.passwordVisible
    },

    async login() {
      // Reset errors
      this.emailError = ''
      this.passwordError = ''

      // --- 1. Append the suffix to the email for API and validation ---
      let fullEmail = this.email.trim();
      if (fullEmail && !fullEmail.includes('@')) {
        fullEmail = fullEmail + '@gmail.com';
      }

      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      let hasError = false 

      // --- Validation Checks ---
      if (!this.email.trim()) { 
        // Changed error message for consistency with the new design's 'Username' placeholder
        this.emailError = 'Please enter your username!'
        hasError = true
      } else if (!emailPattern.test(fullEmail)) { 
        this.emailError = 'Please enter a valid Novamind email!' 
        hasError = true
      }

      if(!this.password) {
        this.passwordError = 'Please enter your password!'
        hasError = true
      }
      
      if (hasError) {
          return
      }

      // --- Supabase Login with Loading State ---
      try {
        this.loading = true // Start loading

        const { data, error } = await supabase.auth.signInWithPassword({
          email: fullEmail,
          password: this.password,
        });

        if (error) {
          throw new Error(error.message); 
        }
        
        console.log('Login successful:', data.user);
        this.$router.push('/app'); 
      } catch (error) {
        console.error('Login error:', error)
        
        const errorMessage = error.message || 'Login failed. Please try again.';
        
        // Handle common Supabase error messages
        if (errorMessage.toLowerCase().includes('invalid login credentials')) {
          this.emailError = 'Invalid username or password.';
          this.passwordError = 'Invalid username or password.';
        } else if (errorMessage.toLowerCase().includes('email not confirmed')) {
          this.emailError = 'Please verify your email address before logging in.';
        } else {
           // Fallback for any other unexpected errors
          this.emailError = errorMessage;
        }

      } finally {
        this.loading = false // Stop loading
      }
    },

    goToSignup() {
      this.$router.push('/signup')
    }
  },
}
</script>

<style>
/* --- 1. Global & Page Layout --- */
:root {
  --primary-color: #3713ec;
  --background-light: #f6f6f8;
  --background-dark: #131022;
  --text-primary: #131022;
  --text-secondary: #594c9a;
  --primary-border-10: rgba(55, 19, 236, 0.1);
  --primary-border-20: rgba(55, 19, 236, 0.2);
  --primary-shadow-10: rgba(55, 19, 236, 0.1);
  --primary-shadow-30: rgba(55, 19, 236, 0.3);
  --primary-ring-50: rgba(55, 19, 236, 0.5);
}

body {
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  margin: 0;
  color: var(--text-primary);
}

.app-screen {
  position: relative;
  display: flex;
  min-height: 100vh;
  width: 100%;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--background-light);
  overflow: hidden;
}

/* --- 2. Background Image & Overlay --- */
.background-image {
  position: absolute;
  inset: 0;
  z-index: 0;
  background-size: cover;
  background-position: center;
}

.background-overlay {
  position: absolute;
  inset: 0;
  z-index: 0;
  /* From bg-background-dark/50 */
  background-color: rgba(19, 16, 34, 0.5);
}

/* --- 3. Main Content Wrapper --- */
.content-wrapper {
  position: relative;
  z-index: 10;
  display: flex;
  width: 100%;
  max-width: 28rem; /* 448px, from max-w-md */
  flex-direction: column;
  align-items: center;
  padding: 1rem; /* 16px, from p-4 */
}

/* --- 4. Login Form Container --- */
.login-container {
  width: 100%;
  border-radius: 0.75rem; /* 12px, from rounded-xl */
  border: 1px solid var(--primary-border-10);
  background-color: #ffffff;
  padding: 2.5rem; /* 40px, from p-8 */
  /* From shadow-2xl shadow-primary/10 */
  box-shadow: 0 25px 50px -12px var(--primary-shadow-10);
  box-sizing: border-box;
}

/* --- 5. Header & Logo --- */
.login-header {
  width: 100%;
}

.header-logo-wrapper {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: center;
  gap: 0.5rem; /* 8px, from gap-2 */
  margin-bottom: 0.5rem; /* 8px, from mb-2 */
}

.logo-svg {
  color: var(--primary-color);
  width: 2rem; /* 32px, from size-8 */
  height: 2rem; /* 32px, from size-8 */
}

.login-container h1 {
  font-size: 1.875rem; /* 30px, from text-3xl */
  line-height: 2.25rem; /* 36px */
  font-weight: 700;
  letter-spacing: -0.025em; /* from tracking-tight */
  color: var(--text-primary);
  margin: 0;
}

.header-subtitle {
  text-align: center;
  font-size: 1rem; /* 16px, from text-base */
  color: var(--text-secondary);
  padding-bottom: 2rem; /* 32px, from pb-8 */
  margin: 0;
}

/* --- 6. Form & Input Fields --- */
.login-form {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 1.25rem; /* 20px, from gap-5 */
}

.input-field-group {
  display: flex;
  width: 100%;
  flex-direction: column;
  /* FIX 1: Set position relative for absolute error anchoring (Matching Signup) */
  position: relative; 
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
}

.input-icon {
  position: absolute;
  left: 1rem; /* 16px, from left-4 */
  font-size: 1.25rem; /* 20px, from text-xl */
  color: var(--text-secondary);
  /* material-symbols-outlined specific fix */
  line-height: 1;
}

.form-input {
  height: 3rem; /* 48px, from h-12 */
  width: 100%;
  min-width: 0;
  flex: 1 1 0%;
  border-radius: 0.5rem; /* 8px, from rounded-lg */
  border: 1px solid var(--primary-border-20);
  background-color: var(--background-light);
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  font-size: 1rem; /* 16px, from text-base */
  color: var(--text-primary);
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-input::placeholder {
  color: var(--text-secondary);
}

/* Input-specific paddings - MATCHING SIGNUP.VUE */
input[placeholder='Email'] {
  padding-left: 1rem; /* Standard left padding */
  padding-right: 8rem; /* Space for suffix */
}

input[placeholder='Password'] {
  padding-left: 1rem; /* Standard left padding */
  padding-right: 3.5rem; /* Space for the smaller password toggle */
}

.form-input:focus {
  border-color: var(--primary-color);
  outline: none;
  /* from focus:ring-2 focus:ring-primary/50 */
  box-shadow: 0 0 0 2px var(--primary-ring-50);
}

.email-suffix {
  position: absolute;
  right: 1rem; /* 16px, from right-4 */
  font-size: 1rem; /* 16px, from text-base */
  color: var(--text-secondary);
  pointer-events: none;
}

/* Password Toggle - MATCHING SIGNUP.VUE */
.password-toggle {
  position: absolute;
  right: 1rem; /* 16px, from right-4 */
  color: var(--text-secondary);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
  height: 100%; /* Ensures vertical centering */
}
.password-toggle .material-symbols-outlined {
  /* Smaller and bolder font, matching Signup */
  font-size: 1rem;
  font-weight: bold;
}

.password-toggle:hover {
  color: var(--primary-color);
}

/* --- 7. Links & Buttons --- */
.forgot-password-link {
  font-size: 0.875rem; /* 14px, from text-sm */
  padding-top: 0.5rem; /* 8px, from pt-2 */
  color: var(--text-secondary);
  text-decoration: underline;
  align-self: flex-end; /* from self-end */
  transition: color 0.2s;
}

.forgot-password-link:hover {
  color: var(--primary-color);
}

.primary-button {
  display: flex;
  height: 3rem; /* 48px, from h-12 */
  width: 100%;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem; /* 8px, from rounded-lg */
  background-color: var(--primary-color);
  padding: 0.75rem 1.5rem; /* 12px 24px, from px-6 py-3 */
  font-size: 1rem; /* 16px, from text-base */
  font-weight: 700; /* from font-bold */
  color: #ffffff;
  border: none;
  cursor: pointer;
  /* From shadow-lg shadow-primary/30 */
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30);
  transition: all 0.2s ease-in-out;
}

.primary-button:hover {
  opacity: 0.9; /* from hover:bg-primary/90 */
}

.primary-button:focus {
  outline: none;
  /* from focus:ring-2 focus:ring-primary ... */
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30),
    0 0 0 2px var(--background-light), 0 0 0 4px var(--primary-color);
}

.primary-button:disabled {
    background-color: #999;
    cursor: not-allowed;
    opacity: 0.7;
    /* Overwrite shadow for disabled state */
    box-shadow: none;
}

/* --- 8. Footer & Signup Link --- */
.signup-link-wrapper {
  padding-top: 2rem; /* 32px, from pt-8 */
  text-align: center;
  font-size: 0.875rem; /* 14px, from text-sm */
  color: var(--text-secondary);
}

.link-button {
  font-weight: 700; /* from font-bold */
  color: var(--primary-color);
  text-decoration: underline;
  transition: color 0.2s;
  border: none;
}

.link-button:hover {
  opacity: 0.8; /* from hover:text-primary/80 */
  cursor: pointer;
}

/* --- Error Styling (Red Border/Glow) --- */
.error-border {
    border-color: red !important; 
    box-shadow: 0 0 0 1px red !important; 
}

/* FIX: Remove complex error box-shadows for the suffix's old box look */
.input-email-wrapper .error-border {
    /* Revert to standard error glow */
    box-shadow: 0 0 0 1px red !important;
}

.input-email-wrapper .error-border + .email-suffix {
    /* Reset all box-related error styling */
    border-color: transparent !important;
    box-shadow: none !important; 
    color: red !important
}

/* FIX 2: Restored absolute positioning to match Signup's visual style and added 2px offset for readability */
.error-input {
    color: red;
    font-size: 0.85em;
    text-align: left;
    min-height: 1.2em;
    margin: 0; /* Remove existing margins */
    
    position: absolute;
    /* Adjusted from 'top: 100%' to give a small gap */
    top: calc(100% + 2px); /* Pushes the error message 2px down from the input field's bottom */
    left: 0;
    width: 100%;

    /* Removed padding-top, as 'top' handles the spacing now */
}
</style>