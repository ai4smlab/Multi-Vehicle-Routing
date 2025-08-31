'use client';
import { create } from 'zustand';
import { UI_WAYPOINTS_FILEID } from '@/constants/fileIds';

const useWaypointStore = create((set) => ({
  waypoints: [],
  waypointsVisible: true,
  hoveredWaypoint: null,

  addWaypoint: ({
    coordinates,
    id = Date.now(),
    demand = 1,
    capacity = null,
    serviceTime = null,
    timeWindow = null,
    pairId = null,
    type = 'Delivery', // Default to Delivery
    fileId = UI_WAYPOINTS_FILEID, // <- default to UI “virtual file”
  }) =>
    set((state) => ({
      waypoints: [
        ...state.waypoints,
        { id, coordinates, demand, capacity, serviceTime, timeWindow, pairId, type, fileId },
      ],
    })),

  setWaypoints: (wps) => set({ waypoints: wps }),
  resetWaypoints: () => set({ waypoints: [] }),

  removeWaypoint: (index) =>
    set((state) => ({
      waypoints: state.waypoints.filter((_, i) => i !== index),
    })),

  moveWaypoint: (index, direction) =>
    set((state) => {
      const newWaypoints = [...state.waypoints];
      const targetIndex = index + direction;
      if (index < 0 || targetIndex < 0 || targetIndex >= newWaypoints.length) return {};
      [newWaypoints[index], newWaypoints[targetIndex]] = [newWaypoints[targetIndex], newWaypoints[index]];
      return { waypoints: newWaypoints };
    }),

  toggleWaypointsVisible: () =>
    set((state) => ({ waypointsVisible: !state.waypointsVisible })),

  setHoveredWaypoint: (wp) => set({ hoveredWaypoint: wp }),
  clearHoveredWaypoint: () => set({ hoveredWaypoint: null }),

  removeWaypointsByFileId: (fileId) => {
    set((state) => {
      const updated = state.waypoints.filter((wp) => wp.fileId !== fileId);
      return { waypoints: updated };
    });
  }
}));

export default useWaypointStore;
