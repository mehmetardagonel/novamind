import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,          // ✅ persist, but only in sessionStorage
    storage: sessionStorage,       // ✅ killed when tab/browser closes
    detectSessionInUrl: true,      // ✅ needed for OAuth/magic links
    // autoRefreshToken: true      // optional, leave as default or set explicitly
  }
})