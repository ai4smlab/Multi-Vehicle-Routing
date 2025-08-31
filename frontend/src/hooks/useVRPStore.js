'use client';
import { create } from 'zustand';
import fitToFeatures from '@/components/map/fitToFeatures';
import useWaypointStore from '@/hooks/useWaypointStore';

const useVrpStore = create((set, get) => ({
  GeojsonFiles: [],

  setGeojsonFiles: (files) => set({ GeojsonFiles: files }),

  addGeojsonFile: (file) =>
    set((state) => ({
      GeojsonFiles: [...state.GeojsonFiles, file],
    })),

  removeGeojsonFile: (id) =>
    set((state) => ({
      GeojsonFiles: state.GeojsonFiles.filter((f) => f.id !== id),
    })),

  toggleFileVisibility: (id) =>
    set((state) => {
      const updatedFiles = state.GeojsonFiles.map(f =>
        f.id === id ? { ...f, visible: !f.visible } : f
      );

      // Find the file
      const file = state.GeojsonFiles.find(f => f.id === id);

      // Check if the file contains waypoint-like features
      const containsWaypoints = file?.data?.features?.some(ft => {
        const props = ft.properties || {};
        const hasSourceWaypoint = props.source === 'waypoint';
        const isOldWaypoint = typeof props.demand !== 'undefined' && Array.isArray(ft.geometry?.coordinates);
        return hasSourceWaypoint || isOldWaypoint;
      });

      if (containsWaypoints) {
        const toggleWaypointsVisible = useWaypointStore.getState().toggleWaypointsVisible;
        toggleWaypointsVisible();
      }

      return { GeojsonFiles: updatedFiles };
    }),

  zoomToFile: (name, setViewState) => {
    const file = get().GeojsonFiles.find((f) => f.name === name);
    if (!file?.data?.features?.length) return;
    fitToFeatures(file.data.features, { setViewState });
  },
}));

export default useVrpStore;
