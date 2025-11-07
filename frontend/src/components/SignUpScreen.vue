<template>
  <div class="signup">
    <h1>Create a Novamind.AI Account</h1>
    <h3>Join your personal AI Email Assistant</h3>

    <div class="signup-form">
      <label>Email</label>
      <input
        type="email"
        v-model="email"
        placeholder="Enter your email"
        @keyup.enter="signup"
      />

      <label>Username</label>
      <input
        type="text"
        v-model="username"
        placeholder="Choose a username"
        @keyup.enter="signup"
      />

      <label>Full Name (Optional)</label>
      <input
        type="text"
        v-model="fullName"
        placeholder="Enter your full name"
        @keyup.enter="signup"
      />

      <label>Password</label>
      <input
        type="password"
        v-model="password"
        placeholder="Create a password"
        @keyup.enter="signup"
      />

      <label>Confirm Password</label>
      <input
        type="password"
        v-model="confirmPassword"
        placeholder="Confirm your password"
        @keyup.enter="signup"
      />
    </div>

    <button @click="signup" :disabled="loading">
      {{ loading ? 'Creating Account...' : 'Sign Up' }}
    </button>

    <p>
      Already have an account?
      <button class="link-button" @click="goToLogin">Log In</button>
    </p>

    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="success">{{ successMessage }}</p>
  </div>
</template>

<script>
import { useAuthStore } from '../stores/auth'

export default {
  data() {
    return {
      email: '',
      username: '',
      fullName: '',
      password: '',
      confirmPassword: '',
      errorMessage: '',
      successMessage: '',
      loading: false,
    }
  },
  setup() {
    const authStore = useAuthStore()
    return { authStore }
  },
  methods: {
    async signup() {
      this.errorMessage = ''
      this.successMessage = ''

      // Validation
      if (!this.email || !this.username || !this.password || !this.confirmPassword) {
        this.errorMessage = 'Please fill in all required fields!'
        return
      }

      const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
      if (!emailPattern.test(this.email)) {
        this.errorMessage = 'Please enter a valid email!'
        return
      }

      if (this.password !== this.confirmPassword) {
        this.errorMessage = 'Passwords do not match!'
        return
      }

      if (this.password.length < 6) {
        this.errorMessage = 'Password must be at least 6 characters!'
        return
      }

      try {
        this.loading = true
        await this.authStore.signup({
          email: this.email,
          username: this.username,
          password: this.password,
          full_name: this.fullName || undefined,
        })

        this.successMessage = 'Account created successfully! Redirecting...'
        console.log('Signup successful')

        // Redirect after 1 second
        setTimeout(() => {
          this.$router.push('/app')
        }, 1000)
      } catch (error) {
        console.error('Signup error:', error)
        this.errorMessage = error.detail || 'Signup failed. Please try again.'
      } finally {
        this.loading = false
      }
    },

    goToLogin() {
      this.$router.push('/login')
    }
  },
}
</script>

<style scoped>
.signup {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  text-align: center;
  background-color: #f7f7f7;
}

.signup-form {
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

.signup-form label {
  text-align: left;
  margin-bottom: 5px;
  font-weight: bold;
}

.signup-form input {
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

.success {
  color: green;
  margin-top: 10px;
}
</style>