<template>
  <div class="login">
    <h1>Welcome to Novamind.AI</h1>
    <h3>Your personal AI Email Assistant</h3>

    <div class="login-form">
      <label>Email</label>
      <input
        type="text"
        v-model="email"
        placeholder="Enter your email or username"
        @keyup.enter="login"
      />

      <label>Password</label>
      <input
        type="password"
        v-model="password"
        placeholder="Enter your password"
        @keyup.enter="login"
      />
    </div>

    <button @click="login" :disabled="loading">
      {{ loading ? 'Logging in...' : 'Login' }}
    </button>

    <p>
      Don't have an account?
      <button class="link-button" @click="goToSignup">Sign Up</button>
    </p>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </div>
</template>

<script>
import { supabase } from '@/database/supabaseClient'

export default {
  data() {
    return {
      email: '',
      password: '',
      errorMessage: '',
      loading: false,
    }
  },
  methods: {
    async login() {
      this.errorMessage = ''

      if (!this.email || !this.password) {
        this.errorMessage = 'Please enter both email and password!'
        return
      }

      try {
        this.loading = true

        // Append @gmail.com suffix if not present
        let fullEmail = this.email.trim()
        if (fullEmail && !fullEmail.includes('@')) {
          fullEmail = fullEmail + '@gmail.com'
        }

        const { data, error } = await supabase.auth.signInWithPassword({
          email: fullEmail,
          password: this.password,
        })

        if (error) throw error

        console.log('Login successful', data)
        this.$router.push('/app')
      } catch (error) {
        console.error('Login error:', error)
        this.errorMessage = error.message || 'Login failed. Please check your credentials.'
      } finally {
        this.loading = false
      }
    },

    goToSignup() {
      this.$router.push('/signup')
    }
  },
}
</script>

<style scoped>
.login {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  text-align: center;
  background-color: #f7f7f7; /* Adding styles for better centering */
}

.login-form {
  display: flex;
  flex-direction: column;
  width: 300px;
  margin: 20px 0;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: white;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.login-form label {
  text-align: left;
  margin-bottom: 5px;
  font-weight: bold;
}

.login-form input {
  padding: 10px;
  margin-bottom: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  padding: 10px 20px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
  margin-top: 10px;
}

button:hover {
  background-color: #0056b3;
}

/* Style for the 'Sign Up' link button */
.link-button {
  background: none;
  color: #007bff;
  border: none;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
  font-size: inherit;
  margin-top: 0;
}

.link-button:hover {
  background: none;
  color: #0056b3;
}

.error {
  color: red;
  margin-top: 10px;
}
</style>