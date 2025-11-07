<template>
  <div class="login">
    <h1>Welcome to Novamind.AI</h1>
    <h3>Your personal AI Email Assistant</h3>

    <div class="login-form">
      <label>Username</label>
      <input
        type="text"
        v-model="username"
        placeholder="Enter your username"
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
import { useAuthStore } from '../stores/auth'

export default {
  data() {
    return {
      username: '',
      password: '',
      errorMessage: '',
      loading: false,
    }
  },
  setup() {
    const authStore = useAuthStore()
    return { authStore }
  },
  methods: {
    async login() {
      this.errorMessage = ''

      if (!this.username || !this.password) {
        this.errorMessage = 'Please enter both username and password!'
        return
      }

      try {
        this.loading = true
        await this.authStore.login(this.username, this.password)
        console.log('Login successful')
        this.$router.push('/app')
      } catch (error) {
        console.error('Login error:', error)
        this.errorMessage = error.detail || 'Login failed. Please check your credentials.'
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