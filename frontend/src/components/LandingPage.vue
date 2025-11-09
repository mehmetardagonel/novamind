<template>
  <div class="landing-page-wrapper">
    <header class="header">
      <div class="header-content">
        <div class="header-left">
          <div class="logo-container">
            <div class="logo-icon">
              <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path d="M24 45.8096C19.6865 45.8096 15.4698 44.5305 11.8832 42.134C8.29667 39.7376 5.50128 36.3314 3.85056 32.3462C2.19985 28.361 1.76794 23.9758 2.60947 19.7452C3.451 15.5145 5.52816 11.6284 8.57829 8.5783C11.6284 5.52817 15.5145 3.45101 19.7452 2.60948C23.9758 1.76795 28.361 2.19986 32.3462 3.85057C36.3314 5.50129 39.7376 8.29668 42.134 11.8833C44.5305 15.4698 45.8096 19.6865 45.8096 24L24 24L24 45.8096Z"></path>
              </svg>
            </div>
            <h2 class="logo-text">Novamind.AI</h2>
          </div>
          <div class="nav-links">
            </div>
        </div>
        <div class="header-right">
          <button class="btn btn-secondary" @click="goToLogin">
            <span class="btn-text">Log In</span>
          </button>
          <button class="btn btn-primary" @click="goToSignUp">
            <span class="btn-text">Sign Up</span>
          </button>
        </div>
      </div>
    </header>

    <main class="main-content">
      <div class="container">
        <section class="section hero-section">
          <div
            class="hero-card"
            :style="{ backgroundImage: 'url(\'https://lh3.googleusercontent.com/aida-public/AB6AXuBbS-M697yxMAF27F26C7VZxm-8HHZANQjWjZnXGCvjwsdxsMiCzyqjalCOE0-SJI_Rh5pSlspgM1ul0fz9qIR7zPb8SkjESaDyWfR6UQx3-Uv7NlIcikx8cALbiHmz2QcGFFTf96T4ahwuPyqNEga7LUde1_du-6yuOd6fm4u81X_1h8TBc3PeJmk82F9KEcuFRn97afcw-c8f2IODlIdTATtDYgdqzpzZJ_QiIE5wDO3XCnLTowSCY0Yap-BUBswm4RlBaxjf4co\')' }"
          >
            <div class="hero-gradient-overlay"></div>
            <div class="hero-text-content">
              <div class="hero-headings">
                <h1 class="hero-title">
                  Reclaim Your Inbox. Write Better Emails, 10x Faster.
                </h1>
                <h2 class="hero-subtitle">
                  Novamind is the AI assistant that helps you craft perfect emails in seconds, so you can focus on what matters.
                </h2>
              </div>
              <div class="hero-cta">
                <button class="btn btn-primary btn-lg" @click="goToLogin">
                  <span class="btn-text" >Try Novamind for Free</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        <section class="section features-section">
          <div class="features-content">
            <div class="section-header">
              <h2 class="section-title">
                Everything you need to write smarter, not harder
              </h2>
              <p class="section-subtitle">
                Our powerful AI is designed to streamline your workflow and elevate your communication.
              </p>
            </div>
            <div class="features-grid">
              <div class="feature-card">
                <div class="feature-icon-wrapper"><span class="feature-icon material-symbols-outlined">bolt</span></div>
                <div class="feature-text">
                  <h3 class="feature-title">Write Faster</h3>
                  <p class="feature-description">Save hours every week by generating drafts and replies in an instant.</p>
                </div>
              </div>
              <div class="feature-card">
                <div class="feature-icon-wrapper"><span class="feature-icon material-symbols-outlined">account_circle</span></div>
                <div class="feature-text">
                  <h3 class="feature-title">Personalize Instantly</h3>
                  <p class="feature-description">Tailor every message to your audience with smart personalization suggestions.</p>
                </div>
              </div>
              <div class="feature-card">
                <div class="feature-icon-wrapper"><span class="feature-icon material-symbols-outlined">auto_awesome</span></div>
                <div class="feature-text">
                  <h3 class="feature-title">Improve Your Tone</h3>
                  <p class="feature-description">Ensure your emails sound professional, friendly, and effective every time.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="section how-it-works-section">
          <h2 class="how-it-works-title">How It Works</h2>
          <div class="how-it-works-grid">
            <div class="step-card">
              <div class="step-icon-wrapper"><span class="step-icon material-symbols-outlined">edit</span></div>
              <div class="step-text">
                <h3 class="step-title">1. Draft</h3>
                <p class="step-description">Start with a simple prompt or a rough draft of your email.</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-icon-wrapper"><span class="step-icon material-symbols-outlined">magic_button</span></div>
              <div class="step-text">
                <h3 class="step-title">2. Refine</h3>
                <p class="step-description">Let our AI enhance your text for clarity, tone, and impact.</p>
              </div>
            </div>
            <div class="step-card">
              <div class="step-icon-wrapper"><span class="step-icon material-symbols-outlined">send</span></div>
              <div class="step-text">
                <h3 class="step-title">3. Send</h3>
                <p class="step-description">Send your perfectly polished email with confidence in seconds.</p>
              </div>
            </div>
          </div>
        </section>

        <section class="section cta-section">
          <div class="cta-card">
            <div class="cta-content">
              <h2 class="cta-title">Ready to Transform Your Inbox?</h2>
              <p class="cta-subtitle">Join thousands of professionals who are writing better emails faster. Get started with Novamind for free today—no credit card required.</p>
              <div class="cta-button-wrapper">
                <button class="btn btn-primary btn-lg"  @click="goToLogin" >
                  <span class="btn-text">Start Writing for Free</span>
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <footer class="footer">
      <div class="footer-content">
        <div class="footer-inner">
          <div class="footer-left">
            <p>© 2025 Novamind.AI.</p>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>

export default{
    methods: {
        goToLogin() {
          this.$router.push('/login');
        },
        goToSignUp() {
          this.$router.push('/signup');
        }
    },
}
    

</script>

<style scoped>
/* Color Palette (Defined on the component's root element) */
.landing-page-wrapper {
  --primary: rgb(55, 19, 236);
  --background-light: #FFFFFF;
  --surface-light: #F7FAFC;
  --text-light-primary: #1A202C;
  --text-light-secondary: #718096;
  --border-light: #E2E8F0;
  --slate-200: #e2e8f0;

  /* Base font from tailwind.config.js */
  font-family: "Inter", sans-serif;
  
  /* Base layout styles */
  position: relative;
  display: flex;
  min-height: 100vh;
  width: 100%;
  flex-direction: column;
}

/* Base Layout */
.main-content {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: center;
}
.container {
  width: 100%;
  max-width: 1152px; /* 72rem or max-w-6xl */
  padding-left: 1rem;
  padding-right: 1rem;
}
.section {
  padding-top: 4rem; /* py-16 */
  padding-bottom: 4rem;
}
@media (min-width: 768px) {
  .section {
    padding-top: 6rem; /* md:py-24 */
    padding-bottom: 6rem;
  }
}

/* Base Components: Buttons */
.btn {
  display: flex;
  min-width: 84px;
  max-width: 480px;
  cursor: pointer;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 0.5rem; /* rounded-lg */
  height: 2.5rem; /* h-10 */
  padding-left: 1rem; /* px-4 */
  padding-right: 1rem;
  font-size: 0.875rem; /* text-sm */
  font-weight: 700;
  line-height: 1.5; /* leading-normal */
  letter-spacing: 0.015em;
  border: none;
  transition: opacity 0.2s ease;
}
.btn:hover {
  opacity: 0.9;
}
.btn-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.btn-primary {
  background-color: var(--primary);
  color: white;
}
.btn-secondary {
  background-color: rgba(59, 130, 246, 0.1); /* primary/10 */
  color: var(--primary);
}
.btn-lg {
  height: 3rem; /* h-12 */
  padding-left: 1.5rem; /* px-6 */
  padding-right: 1.5rem;
  font-size: 1rem; /* text-base */
}

/* Base Components: Section Headers */
.section-header {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  text-align: center;
}
.section-title {
  letter-spacing: -0.025em; /* tracking-tighter */
  font-size: 1.875rem; /* text-3xl */
  font-weight: 700;
  line-height: 1.25;
}
.section-subtitle {
  font-size: 1.125rem; /* text-lg */
  line-height: 1.5;
  color: var(--text-light-secondary);
  max-width: 768px; /* max-w-3xl */
  margin-left: auto;
  margin-right: auto;
}
@media (min-width: 480px) {
  .section-title {
    font-size: 2.25rem; /* @[480px]:text-4xl */
    font-weight: 900; /* @[480px]:font-black */
  }
}

/* Header */
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgb(55, 19, 236);
  background-color: var(--background-light);
}
.header-content {
  display: flex;
  width: 100%;
  max-width: 1152px; /* max-w-6xl */
  align-items: center;
  justify-content: space-between;
  white-space: nowrap;
  padding: 0.75rem 1rem; /* px-4 py-3 */
}
.header-left {
  display: flex;
  align-items: center;
  gap: 3rem; /* gap-12 */
  color: var(--text-light-primary);
}
.logo-container {
  display: flex;
  align-items: center;
  gap: 1rem; /* gap-4 */
}
.logo-icon {
  width: 1.5rem; /* size-6 */
  height: 1.5rem;
  color: var(--primary);
}
.logo-text {
  font-size: 1.125rem; /* text-lg */
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.015em;
}
.nav-links {
  display: none;
  align-items: center;
  gap: 2rem; /* gap-8 */
}
@media (min-width: 768px) {
  .nav-links {
    display: flex; /* md:flex */
  }
}
.header-right {
  display: flex;
  flex: 1;
  justify-content: flex-end;
  gap: 0.5rem; /* gap-2 */
}

/* Hero Section */
.hero-card {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.75rem; /* rounded-xl */
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  overflow: hidden; /* Added to ensure overlay respects border radius */
}
.hero-gradient-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background-image: linear-gradient(to top, rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.2), transparent);
}
.hero-text-content {
  position: relative;
  z-index: 10;
  display: flex;
  width: 100%;
  max-width: 576px; /* max-w-2xl */
  flex-direction: column;
  gap: 1.5rem; /* gap-6 */
  padding: 2rem; /* p-8 */
  text-align: center;
  color: white;
}
.hero-headings {
  display: flex;
  flex-direction: column;
  gap: 1rem; /* gap-4 */
}
.hero-title {
  font-size: 2.25rem; /* text-4xl */
  font-weight: 900; /* font-black */
  line-height: 1.25;
  letter-spacing: -0.025em; /* tracking-tighter */
}
.hero-subtitle {
  font-size: 1.125rem; /* text-lg */
  font-weight: 400;
  line-height: 1.5;
  color: var(--slate-200); /* text-slate-200 */
}
.hero-cta {
  display: flex;
  justify-content: center;
}
@media (min-width: 768px) {
  .hero-text-content {
    padding: 4rem; /* md:p-16 */
  }
}
@media (min-width: 480px) {
  .hero-title {
    font-size: 3.75rem; /* @[480px]:text-6xl */
  }
  .hero-subtitle {
    font-size: 1.25rem; /* @[480px]:text-xl */
  }
}

/* Features Section */
.features-content {
  display: flex;
  flex-direction: column;
  gap: 2.5rem; /* gap-10 */
}
.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem; /* gap-4 */
}
.feature-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem; /* gap-3 */
  border-radius: 0.75rem; /* rounded-xl */
  border: 1px solid var(--border-light);
  background-color: var(--surface-light);
  padding: 1.5rem; /* p-6 */
}
.feature-icon-wrapper {
  color: var(--primary);
}
.feature-icon {
  font-size: 1.875rem !important; /* !text-3xl */
}
.feature-text {
  display: flex;
  flex-direction: column;
  gap: 0.25rem; /* gap-1 */
}
.feature-title {
  font-size: 1.125rem; /* text-lg */
  font-weight: 700;
  line-height: 1.25;
}
.feature-description {
  font-size: 0.875rem; /* text-sm */
  font-weight: 400;
  line-height: 1.5;
  color: var(--text-light-secondary);
}

/* How It Works Section */
.how-it-works-title {
  text-align: center;
  font-size: 1.875rem; /* text-3xl */
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em; /* tracking-tighter */
  margin-bottom: 2.5rem; /* mb-10 */
}
.how-it-works-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem; /* gap-4 */
}
.step-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem; /* gap-3 */
  border-radius: 0.75rem; /* rounded-xl */
  border: 1px solid var(--border-light);
  background-color: var(--surface-light);
  padding: 1.5rem; /* p-6 */
  text-align: center;
}
.step-icon-wrapper {
  color: var(--primary);
  margin-left: auto;
  margin-right: auto;
}
.step-icon {
  font-size: 1.875rem !important; /* !text-3xl */
}
.step-text {
  display: flex;
  flex-direction: column;
  gap: 0.25rem; /* gap-1 */
}
.step-title {
  font-size: 1.125rem; /* text-lg */
  font-weight: 700;
  line-height: 1.25;
}
.step-description {
  font-size: 0.875rem; /* text-sm */
  font-weight: 400;
  line-height: 1.5;
  color: var(--text-light-secondary);
}

/* CTA Section */
.cta-card {
  border-radius: 0.75rem; /* rounded-xl */
  background-color: rgba(59, 130, 246, 0.1); /* bg-primary/10 */
  padding: 2rem; /* p-8 */
  text-align: center;
}
.cta-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem; /* gap-6 */
  max-width: 576px; /* max-w-2xl */
  margin-left: auto;
  margin-right: auto;
}
.cta-title {
  font-size: 1.875rem; /* text-3xl */
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.025em; /* tracking-tighter */
  color: var(--text-light-primary);
}
.cta-subtitle {
  font-size: 1.125rem; /* text-lg */
  color: var(--text-light-secondary);
}
.cta-button-wrapper {
  display: flex;
  justify-content: center;
}
@media (min-width: 768px) {
  .cta-card {
    padding: 4rem; /* md:p-16 */
  }
}

/* Footer */
.footer {
  width: 100%;
  display: flex;
  justify-content: center;
  border-top: 1px solid var(--border-light);
  margin-top: 4rem; /* mt-16 */
}
.footer-content {
  width: 100%;
  max-width: 1152px; /* max-w-6xl */
  padding: 2rem 1rem; /* px-4 py-8 */
}
.footer-inner {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem; /* gap-6 */
}
.footer-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem; /* gap-4 */
  font-size: 0.875rem; /* text-sm */
  color: var(--text-light-secondary);
}
@media (min-width: 768px) {
  .footer-inner {
    flex-direction: row; /* md:flex-row */
  }
  .footer-left {
    flex-direction: row; /* md:flex-row */
    gap: 1.5rem; /* gap-6 */
  }
}
</style>