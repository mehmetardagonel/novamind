import { createClient } from '@supabase/supabase-js'

const supabaseUrl = 'https://usyutlojgjjkyjrlwfxb.supabase.co'
const supabaseAnonKey = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVzeXV0bG9qZ2pqa3lqcmx3ZnhiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjE5MDY0OTMsImV4cCI6MjA3NzQ4MjQ5M30.7qE31wYQazzFXi4HTJfhm_yTLuHa3FT66EYjGqs0YlA'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
