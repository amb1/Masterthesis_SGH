import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Ion } from 'cesium';

interface CesiumState {
  accessToken: string | null;
  setAccessToken: (token: string) => void;
}

export const useCesiumStore = create<CesiumState>()(
  persist(
    (set) => ({
      accessToken: null,
      setAccessToken: (token: string) => {
        Ion.defaultAccessToken = token;
        set({ accessToken: token });
      },
    }),
    {
      name: 'cesium-storage',
    }
  )
);