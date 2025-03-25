import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase Umgebungsvariablen fehlen');
}

// Erstelle eine einzelne Client-Instanz mit eindeutigem Storage-Key
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    storageKey: 'sgh-master-auth-token',
    storage: window.localStorage
  }
}); 