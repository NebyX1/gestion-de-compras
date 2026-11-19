import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Solo preferencias de accesibilidad, no sensibles: nunca expedientes, ofertas, decisiones ni permisos.
export interface Preferences {
  darkMode: boolean;
  bigText: boolean;
  highContrast: boolean;
  reduceMotion: boolean;
  setPref: (key: 'darkMode' | 'bigText' | 'highContrast' | 'reduceMotion', value: boolean) => void;
}

export const usePreferences = create<Preferences>()(
  persist(
    (set) => ({
      darkMode: false,
      bigText: false,
      highContrast: false,
      reduceMotion: false,
      setPref: (key, value) => set({ [key]: value } as Partial<Preferences>),
    }),
    {
      name: 'compra-clara-preferencias',
      partialize: (s) => ({ darkMode: s.darkMode, bigText: s.bigText, highContrast: s.highContrast, reduceMotion: s.reduceMotion }),
    },
  ),
);
