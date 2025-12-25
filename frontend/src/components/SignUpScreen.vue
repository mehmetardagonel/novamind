<template>
  <div class="app-screen">
    <div class="background-image"></div>
    <div class="background-overlay"></div>

    <div class="content-wrapper">
      <main class="login-container">
        <div class="login-header">
          <a class="header-logo-wrapper logo-link">

            <div class="logo-icon-container">
              <div class="logo-svg novamind-logo">
                <svg fill="none" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"
                    fill="currentColor"
                  ></path>
                </svg>
              </div>

            </div>

            <h1 class="logo-text">Novamind.AI</h1>
          </a>
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
                  <span class="material-symbols-outlined icon-adjust">
                    {{ passwordVisible ? "visibility_off" : "visibility" }}
                  </span>
                </button>
              </div>
              <p v-if="passwordError" class="error-input">
                {{ passwordError }}
              </p>
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
                  <span class="material-symbols-outlined icon-adjust">
                    {{
                      confirmPasswordVisible ? "visibility_off" : "visibility"
                    }}
                  </span>
                </button>
              </div>
              <p v-if="confirmPasswordError" class="error-input">
                {{ confirmPasswordError }}
              </p>
            </label>
          </div>

          <button
            @click="signup"
            class="primary-button"
            :disabled="loading"
            type="submit"
          >
            {{ loading ? "Creating Account..." : "Sign Up" }}
          </button>
        </form>

        <div class="signup-link-wrapper">
          <p>
            Already have an account?
            <a @click.prevent="goToLogin" class="link-button" href="#"
              >Log In</a
            >
          </p>
          <p v-if="successMessage" class="success-message">
            {{ successMessage }}
          </p>
        </div>
      </main>
    </div>
  </div>
</template>

<script>
import { supabase } from '@/database/supabaseClient'

export default {
  data() {
    return {
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
      this.successMessage = "";
      this.emailError = "";
      this.passwordError = "";
      this.confirmPasswordError = "";

      let hasError = false;

      // Append @gmail.com suffix if not present
      let fullEmail = this.email.trim();
      if (fullEmail && !fullEmail.includes("@")) {
        fullEmail = fullEmail + "@gmail.com";
      }

      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

      if (!this.email.trim()) {
        this.emailError = "Please enter your email!";
        hasError = true;
      } else if (!emailPattern.test(fullEmail)) {
        this.emailError = "Please enter a valid email!";
        hasError = true;
      }

      if (!this.password) {
        this.passwordError = "Please enter your password!";
        hasError = true;
      } else if (this.password.length < 6) {
        this.passwordError = "Password must be at least 6 characters!";
        hasError = true;
      }

      if (!this.confirmPassword) {
        this.confirmPasswordError = "Please confirm your password!";
        hasError = true;
      }

      if (
        this.password &&
        this.confirmPassword &&
        this.password !== this.confirmPassword
      ) {
        this.passwordError = "Passwords do not match!";
        this.confirmPasswordError = "Passwords do not match!";
        hasError = true;
      }

      // 2. Stop if validation fails
      if (hasError) {
        return;
      }

      try {
        this.loading = true;

        const { data, error } = await supabase.auth.signUp({
          email: fullEmail,
          password: this.password,
        });

        // 3. Check for explicit errors (e.g., password policy violation)
        if (error) {
          throw error;
        }

        // 4. CHECK FOR ALREADY CONFIRMED USER
        if (
          data.user &&
          data.user.identities &&
          data.user.identities.length === 0
        ) {
          this.emailError = "You already have an account. Please log in.";
          this.passwordError = "";
          this.confirmPasswordError = "";
          return;
        }

        // 5. CHECK FOR NEW/UNCONFIRMED USER
        if (!data.user) {
          this.emailError =
            "This user already exists. If your account is not verified, check your email.";
          return;
        }

        // 6. SUCCESS
        this.successMessage =
          "Account created successfully! Please check your email to verify your account.";
        console.log("Signup successful", data);
      } catch (error) {
        console.error("Signup error:", error);

        const errorMessage =
          error.message || "Signup failed. Please try again.";

        if (errorMessage.toLowerCase().includes("password")) {
          this.passwordError = errorMessage;
        } else {
          this.emailError = errorMessage;
        }
      } finally {
        this.loading = false;
      }
    },

    goToLogin() {
      this.$router.push("/login");
    },
  },
};
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
  font-family: "Inter", sans-serif;
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
  background-color: rgba(207, 203, 255, 0.5);
}

/* --- 3. Main Content Wrapper --- */
.content-wrapper {
  position: relative;
  z-index: 10;
  display: flex;
  width: 100%;
  max-width: 28rem;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
}

/* --- 4. Login Form Container --- */
.login-container {
  width: 100%;
  max-width: 28rem;
  min-height: 28rem;
  border-radius: 0.75rem;
  border: 1px solid var(--primary-border-10);
  background-color: #ffffff;
  padding: 2.5rem;
  box-shadow: 0 25px 50px -12px var(--primary-shadow-10);
  box-sizing: border-box;
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
    width: 2rem;
    height: 2rem;
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
    z-index: 2;
}

/* The Novamind.AI Text Label (STATIC) */
.logo-text {
    font-size: 1.875rem;
    line-height: 2.25rem;
    font-weight: 700;
    letter-spacing: -0.025em;
    margin: 0;
    transition: color 0.3s ease;
    opacity: 1;
    color: var(--text-primary);
}

.header-subtitle {
  text-align: center;
  font-size: 1rem;
  color: var(--text-secondary);
  padding-bottom: 2rem;
  margin: 0;
}

/* --- 6. Form & Input Fields --- */
.login-form {
  display: flex;
  width: 100%;
  flex-direction: column;
  gap: 1.25rem;
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
  height: 3rem;
  width: 100%;
  min-width: 0;
  flex: 1 1 0%;
  border-radius: 0.5rem;
  border: 1px solid var(--primary-border-20);
  background-color: var(--background-light);
  padding-top: 0.75rem;
  padding-bottom: 0.75rem;
  font-size: 1rem;
  color: var(--text-primary);
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-input::placeholder {
  color: var(--text-secondary);
}

/* Input-specific paddings */
input[placeholder="Email"] {
  padding-left: 1rem;
  padding-right: 8rem;
}

input[placeholder="Password"],
input[placeholder="Confirm Password"] {
  padding-left: 1rem;
  padding-right: 3.5rem;
}

.form-input:focus {
  border-color: var(--primary-color);
  outline: none;
  box-shadow: 0 0 0 2px var(--primary-ring-50);
  background-color: #ffffff;
}

.input-wrapper input:focus + .email-suffix {
  color: var(--text-primary);
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

/* New: Styling for the icon element itself */
.password-toggle .icon-adjust {
  font-size: 1.5rem;
  font-weight: normal;
}

.password-toggle:hover {
  color: var(--primary-color);
}

/* --- 7. Links & Buttons --- */
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
  margin-top: 10px;
}

.primary-button:hover {
  opacity: 0.9;
}

.primary-button:focus {
  outline: none;
  box-shadow: 0 10px 15px -3px var(--primary-shadow-30),
    0 4px 6px -4px var(--primary-shadow-30), 0 0 0 2px var(--background-light),
    0 0 0 4px var(--primary-color);
}

/* Disabled state */
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
  cursor: pointer;
}

.link-button:hover {
  opacity: 0.8;
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
  margin: 0;

  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  width: 100%;
}
.input-wrapper .error-border + .email-suffix {
  color: red !important;
}

/* Success Message Styling */
.success-message {
  color: green;
  font-size: 0.9em;
  text-align: center;
  width: 100%;
  margin-top: 10px;
}

/* ========== MOBILE RESPONSIVE ========== */

/* Tablet (≤1024px) */
@media (max-width: 1024px) {
  .signup-container {
    padding: 2rem;
  }

  .logo-text {
    font-size: 1.6rem;
  }
}

/* Mobile (≤768px) */
@media (max-width: 768px) {
  .content-wrapper {
    padding: 0.5rem;
  }

  .signup-container {
    padding: 1.5rem;
    min-height: auto;
  }

  .logo-text {
    font-size: 1.5rem;
  }

  .header-subtitle {
    font-size: 0.9rem;
    padding-bottom: 1.5rem;
  }

  /* Touch-friendly input fields */
  .form-input {
    height: 3.5rem; /* 56px for better touch target */
    font-size: 1rem;
  }

  /* Touch-friendly buttons */
  .primary-button {
    height: 3.5rem;
    min-height: 44px;
    font-size: 1.05rem;
  }

  .password-toggle {
    padding: 0.5rem;
  }

  .password-toggle .icon-adjust {
    font-size: 1.6rem;
  }
}

/* Small Mobile (≤480px) */
@media (max-width: 480px) {
  .signup-container {
    padding: 1.25rem;
    border-radius: 0.5rem;
  }

  .logo-icon-container {
    width: 1.75rem;
    height: 1.75rem;
  }

  .logo-text {
    font-size: 1.35rem;
  }

  .header-subtitle {
    font-size: 0.85rem;
  }

  .signup-form {
    gap: 1rem;
  }

  input[placeholder="Email"] {
    padding-right: 7rem;
  }

  .email-suffix {
    font-size: 0.9rem;
  }
}
</style>
