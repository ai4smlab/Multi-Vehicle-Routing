'use client';
import { create } from 'zustand';

const STORE_ID = Math.random().toString(36).slice(2);

const useMapStore = create((set) => ({
  __id: STORE_ID,

  // Controlled camera (used by MapLibre or legacy callers)
  viewState: { longitude: 0, latitude: 0, zoom: 2, pitch: 0, bearing: 0 },
  setViewState: (next) => set({ viewState: next }),

  // One-shot camera command (consumed by Mapbox/MapLibre components)
  cameraCommand: null,

  issueCameraCommand: (cmd) => {
    // console.debug('[store] issueCameraCommand', cmd);
    set({
      cameraCommand: { ...cmd, _nonce: Date.now() + Math.random() } // ensure change detection
    });
    // console.debug('[store] state.cameraCommand now', JSON.stringify(useMapStore.getState().cameraCommand));
  },

  clearCameraCommand: () => {
    // console.debug('[store] clearCameraCommand');
    set({ cameraCommand: null });
  },
}));

export default useMapStore;
