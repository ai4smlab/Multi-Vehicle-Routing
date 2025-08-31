// src/hooks/useRenderSettingsStore.ts
import { create } from 'zustand';

type GeometrySource = 'auto'|'backend'|'mapbox'|'osrm'|'none';

type State = {
  geometrySource: GeometrySource;
  osrmUrl: string;
  setGeometrySource: (v: GeometrySource) => void;
  setOsrmUrl: (v: string) => void;
};

export const useRenderSettingsStore = create<State>((set) => ({
  geometrySource: (typeof window !== 'undefined' && (localStorage.getItem('geometrySource') as GeometrySource)) || 'auto',
  osrmUrl: (typeof window !== 'undefined' && localStorage.getItem('osrmUrl')) || (process.env.NEXT_PUBLIC_OSRM_URL || 'https://router.project-osrm.org'),
  setGeometrySource: (v) => set(() => { localStorage.setItem('geometrySource', v); return { geometrySource: v }; }),
  setOsrmUrl: (v) => set(() => { localStorage.setItem('osrmUrl', v); return { osrmUrl: v }; }),
}));

export default useRenderSettingsStore;
