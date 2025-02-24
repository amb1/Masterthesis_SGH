import { create } from 'zustand';
import { supabase } from '../lib/supabase';
import type { User } from '@supabase/supabase-js';

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  error: null,
  signIn: async (email, password) => {
    try {
      set({ error: null });
      const { error, data } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      
      if (error) {
        if (error.message === 'Invalid login credentials') {
          throw new Error('Invalid email or password');
        }
        throw error;
      }

      set({ user: data.user, error: null });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
      set({ error: errorMessage });
      throw error;
    }
  },
  signUp: async (email, password) => {
    try {
      set({ error: null });
      const { error, data } = await supabase.auth.signUp({
        email,
        password,
      });

      if (error) {
        if (error.message.includes('already registered')) {
          throw new Error('An account with this email already exists');
        }
        throw error;
      }

      set({ user: data.user, error: null });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
      set({ error: errorMessage });
      throw error;
    }
  },
  signOut: async () => {
    try {
      set({ error: null });
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      set({ user: null, error: null });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
      set({ error: errorMessage });
      throw error;
    }
  },
  clearError: () => set({ error: null }),
}));

// Initialize auth state
supabase.auth.onAuthStateChange((event, session) => {
  useAuthStore.setState({ user: session?.user ?? null, loading: false, error: null });
});

// Get initial session
supabase.auth.getSession().then(({ data: { session } }) => {
  useAuthStore.setState({ user: session?.user ?? null, loading: false });
});