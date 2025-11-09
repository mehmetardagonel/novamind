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
          <a @click.prevent="goToHome" class="header-logo-wrapper logo-link" href="/">
            
            <div class="logo-icon-container">
              <div class="logo-svg novamind-logo">
                <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"
                    fill="currentColor"
                  ></path>
                </svg>
              </div>
              
              <div class="logo-svg home-icon-overlay">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M10 20V14H14V20H19V12H22L12 3L2 12H5V20H10Z"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </div>
            </div>
            
            <h1 class="logo-text">Novamind.AI</h1>
          </a>
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
                  <span class="material-symbols-outlined icon-adjust">
                    {{ passwordVisible ? 'visibility_off' : 'visibility' }}
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
            <a @click.prevent="goToSignup" class="link-button" href="#">Sign Up</a>
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
    // Home navigation method
    goToHome() {
         this.$router.push('/home');
    },

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
        this.$router.push('/signup');
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
  max-width: 28rem;
  min-height: 28rem;
  border-radius: 0.75rem; /* 12px, from rounded-xl */
  border: 1px solid var(--primary-border-10);
  background-color: #ffffff;
  padding: 2.5rem; /* 40px, from p-8 */
  box-shadow: 0 25px 50px -12px var(--primary-shadow-10);
  box-sizing: border-box;
  position: relative; 
}

/* --- 5. Header & Logo (UPDATED FOR ICON-ONLY MORPH) --- */
.login-header {
  width: 100%;
}

/* The logo-link is the primary interactive area */
.logo-link {
    text-decoration: none;
    cursor: pointer;
    position: relative; 
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem; 
    transition: color 0.3s ease;
    margin-bottom: 0.5rem; 
}

/* NEW: Container to manage the two layered icons */
.logo-icon-container {
    position: relative;
    width: 2rem; /* Keep a fixed width for the icons */
    height: 2rem; /* Keep a fixed height for the icons */
}

/* Base style for both icons inside the container */
.logo-svg {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    color: var(--primary-color);
    transition: opacity 0.3s ease, transform 0.3s ease;
}

/* 1. Novamind Logo (Default State) */
.novamind-logo {
    opacity: 1; 
    transform: scale(1); 
    z-index: 2; /* On top when visible */
}

/* 2. Home Icon (Hidden State) */
.home-icon-overlay {
    opacity: 0; 
    transform: scale(0.5); /* Start small */
    z-index: 1; /* Below the Novamind logo by default */
}

/* The Novamind.AI Text Label (STATIC) */
.logo-text {
    font-size: 1.875rem; /* 30px, from text-3xl */
    line-height: 2.25rem; /* 36px */
    font-weight: 700;
    letter-spacing: -0.025em; /* from tracking-tight */
    margin: 0;
    transition: color 0.3s ease; /* Only the color changes */
    opacity: 1; /* Ensure text remains fully visible */
    color: var(--text-primary);
}

/* --- HOVER EFFECT: The Icon Morph --- */

.logo-link:hover .novamind-logo {
    /* Fade and shrink the Novamind logo out */
    opacity: 0;
    transform: scale(0.5) rotate(-90deg);
}

.logo-link:hover .home-icon-overlay {
    /* Fade and grow the Home icon in */
    opacity: 1;
    transform: scale(1);
    
    /* Apply the "Light Switch Glow" effect */
    color: var(--primary-color);
    filter: 
      drop-shadow(0 0 5px var(--primary-color)) 
      drop-shadow(0 0 10px var(--primary-shadow-30));
    z-index: 3; /* Bring to front when active */
}

.logo-link:hover .logo-text {
    /* Change the text color to match the icon color */
    color: var(--primary-color);
}
/* --- End of Hover Changes --- */

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
  position: relative; 
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

input[placeholder='Email'] {
  padding-left: 1rem; 
  padding-right: 8rem; 
}

input[placeholder='Password'] {
  padding-left: 1rem; 
  padding-right: 3.5rem; 
}

.form-input:focus {
  border-color: var(--primary-color);
  outline: none;
  box-shadow: 0 0 0 2px var(--primary-ring-50);
}

.email-suffix {
  position: absolute;
  right: 1rem; 
  font-size: 1rem; 
  color: var(--text-secondary);
  pointer-events: none;
}

.password-toggle {
  position: absolute;
  right: 1rem; 
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

.password-toggle .icon-adjust {
  font-size: 1.5rem; 
  font-weight: normal; 
}


.password-toggle:hover {
  color: var(--primary-color);
}

/* --- 7. Links & Buttons --- */
.forgot-password-link {
  font-size: 0.875rem; 
  padding-top: 0.5rem; 
  color: var(--text-secondary);
  text-decoration: underline;
  align-self: flex-end; 
  transition: color 0.2s;
}

.forgot-password-link:hover {
  color: var(--primary-color);
}

.primary-button {
  display: flex;
  height: 3rem; 
  width: 100%;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem; 
  background-color: var(--primary-color);
  padding: 0.75rem 1.5rem; 
  font-size: 1rem; 
  font-weight: 700; 
  color: #ffffff;
  border: none;
  cursor: pointer;
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30);
  transition: all 0.2s ease-in-out;
}

.primary-button:hover {
  opacity: 0.9; 
}

.primary-button:focus {
  outline: none;
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30),
    0 0 0 2px var(--background-light), 0 0 0 4px var(--primary-color);
}

.primary-button:disabled {
    background-color: #999;
    cursor: not-allowed;
    opacity: 0.7;
    box-shadow: none;
}

/* --- 8. Footer & Signup Link --- */
.signup-link-wrapper {
  padding-top: 2rem; 
  text-align: center;
  font-size: 0.875rem; 
  color: var(--text-secondary);
}

.link-button {
  font-weight: 700; 
  color: var(--primary-color);
  text-decoration: underline;
  transition: color 0.2s;
  border: none;
}

.link-button:hover {
  opacity: 0.8; 
  cursor: pointer;
}

/* --- Error Styling (Red Border/Glow) --- */
.error-border {
    border-color: red !important; 
    box-shadow: 0 0 0 1px red !important; 
}

.input-wrapper .error-border + .email-suffix{
    color: red !important;
    border-color: transparent !important;
    box-shadow: none !important; 
}

.error-input {
    color: red;
    font-size: 0.85em;
    text-align: left;
    min-height: 1.2em;
    margin: 0; 
    
    position: absolute;
    top: calc(100% + 2px); 
    left: 0;
    width: 100%;
}
</style>