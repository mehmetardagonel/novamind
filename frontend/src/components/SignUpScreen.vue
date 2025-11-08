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

        <form class="login-form" @submit.prevent="signup">
          <div class="input-field-group">
            <label>
              <div class="input-wrapper">
                <input
                  v-model="email"
                  class="form-input"
                  placeholder="Email"
                  type="text"
                  :class="{ 'error-border': emailError }"
                  @keyup.enter="signup"
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
                  @keyup.enter="signup"
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

          <div class="input-field-group">
            <label>
              <div class="input-wrapper">
                <input
                  v-model="confirmPassword"
                  class="form-input"
                  placeholder="Confirm Password"
                  :class="{ 'error-border': confirmPasswordError }"
                  :type="confirmPasswordVisible ? 'text' : 'password'"
                  @keyup.enter="signup"
                />
                <button
                  aria-label="Toggle Confirm Password visibility"
                  class="password-toggle"
                  type="button"
                  @click.prevent="toggleConfirmPasswordVisibility"
                >
                  <span class="material-symbols-outlined">
                    {{ confirmPasswordVisible ? 'Hide' : 'Show' }}
                  </span>
                </button>
              </div>
              <p v-if="confirmPasswordError" class="error-input">{{ confirmPasswordError }}</p>
            </label>
          </div>

          <button
            @click="signup"
            class="primary-button"
            :disabled="loading"
            type="submit"
          >
            {{ loading ? 'Creating Account...' : 'Sign Up' }}
          </button>
        </form>

        <div class="signup-link-wrapper">
          <p>
            Already have an account?
            <a @click="goToLogin" class="link-button" href="#">Log In</a>
          </p>
          <p v-if="successMessage" class="success-message">{{ successMessage }}</p>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import BackgroundImage from '@/assets/background.png'; // NEW: Import background image
import { supabase } from '@/database/supabaseClient'

export default {
  data() {
    return {
      backgroundImageUrl: BackgroundImage, // NEW: Added background image data property
      email: '',
      password: '',
      confirmPassword: '',

      successMessage: '',
      loading: false,

      emailError: '',
      passwordError: '',
      confirmPasswordError: '',
      passwordVisible: false,
      confirmPasswordVisible: false,
    }
  },
  methods: {
    togglePasswordVisibility() {
      this.passwordVisible = !this.passwordVisible
    },
    toggleConfirmPasswordVisibility() {
      this.confirmPasswordVisible = !this.confirmPasswordVisible
    },

    async signup() {
      // 1. Reset all errors and success messages
      this.successMessage = ''
      this.emailError = ''
      this.passwordError = ''
      this.confirmPasswordError = ''

      let hasError = false

      // Append @gmail.com suffix if not present
      let fullEmail = this.email.trim()
      if (fullEmail && !fullEmail.includes('@')) {
        fullEmail = fullEmail + '@gmail.com'
      }

      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

      if (!this.email.trim()) {
        this.emailError = 'Please enter your email!'
        hasError = true
      } else if (!emailPattern.test(fullEmail)) {
        this.emailError = 'Please enter a valid email!'
        hasError = true
      }

      if (!this.password) {
        this.passwordError = 'Please enter your password!'
        hasError = true
      } else if (this.password.length < 6) {
        this.passwordError = 'Password must be at least 6 characters!'
        hasError = true
      }

      if (!this.confirmPassword) {
        this.confirmPasswordError = 'Please confirm your password!'
        hasError = true
      }

      if (
        this.password &&
        this.confirmPassword &&
        this.password !== this.confirmPassword
      ) {
        this.passwordError = 'Passwords do not match!'
        this.confirmPasswordError = 'Passwords do not match!'
        hasError = true
      }

      // 2. Stop if validation fails
      if (hasError) {
        return
      }

      try {
        this.loading = true

        const { data, error } = await supabase.auth.signUp({
          email: fullEmail,
          password: this.password,
        })

        // 3. Check for explicit errors (e.g., password policy violation)
        if (error) {
          throw error
        }

        // 4. CHECK FOR ALREADY CONFIRMED USER (The specific logic requested)
        // If the user object exists, but the identities array is empty, the user is already confirmed.
        if (data.user && data.user.identities && data.user.identities.length === 0) {
           this.emailError = 'You already have an account. Please log in.';
           this.passwordError = '';
           this.confirmPasswordError = '';
           return; // Stop execution
        }

        // 5. CHECK FOR NEW/UNCONFIRMED USER (Previous Logic for Empty Data)
        // This generally covers cases where the user exists and the verification email was resent.
        if (!data.user) {
          this.emailError = 'This user already exists. If your account is not verified, check your email.';
          return;
        }

        // 6. SUCCESS: If we reach here, a new user was created.
        this.successMessage =
          'Account created successfully! Please check your email to verify your account.'
        console.log('Signup successful', data)

      } catch (error) {
        console.error('Signup error:', error)

        const errorMessage = error.message || 'Signup failed. Please try again.'

        if (errorMessage.toLowerCase().includes('password')) {
          this.passwordError = errorMessage;
        } else {
          this.emailError = errorMessage;
        }

      } finally {
        this.loading = false
      }
    },

    goToLogin() {
      this.$router.push('/login')
    },
  },
}
</script>

<style scoped>
/*
 * Styles from SignUpScreencss.vue (Corporate Design)
 */

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
  align-items: center;
  justify-content: center;
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
  position: relative; /* Added for error positioning */
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
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

/* Input-specific paddings */
input[placeholder='Email'] {
  padding-left: 1rem; /* Standard left padding */
  padding-right: 8rem; /* Space for suffix */
}

input[placeholder='Password'],
input[placeholder='Confirm Password'] {
  padding-left: 1rem; /* Standard left padding */
  padding-right: 3.5rem;
}

.form-input:focus {
  border-color: var(--primary-color);
  outline: none;
  /* from focus:ring-2 focus:ring-primary/50 */
  box-shadow: 0 0 0 2px var(--primary-ring-50);
  background-color: #ffffff;
}

.input-wrapper input:focus + .email-suffix { /* Added focus color change */
    color: var(--text-primary);
}

.email-suffix {
  position: absolute;
  right: 1rem; /* 16px, from right-4 */
  font-size: 1rem; /* 16px, from text-base */
  color: var(--text-secondary);
  pointer-events: none;
}

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
  height: 100%;
}
.password-toggle .material-symbols-outlined {
  /* Match original corporate design look */
  font-size: 1rem;
  font-weight: bold;
}

.password-toggle:hover {
  color: var(--primary-color);
}

/* --- 7. Links & Buttons --- */
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
  margin-top: 10px;
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

/* Disabled state */
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
  cursor: pointer;
}

.link-button:hover {
  opacity: 0.8; /* from hover:text-primary/80 */
}

/* --- Error Styling (Red Border/Glow) --- */
.error-border {
    border-color: red !important;
    box-shadow: 0 0 0 1px red !important;
}

/* Error text positioning and style */
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
.input-wrapper .error-border + .email-suffix {
    color: red !important
}

/* Success Message Styling */
.success-message {
    color: green;
    font-size: 0.9em;
    text-align: center;
    width: 100%;
    margin-top: 10px;
}
</style>