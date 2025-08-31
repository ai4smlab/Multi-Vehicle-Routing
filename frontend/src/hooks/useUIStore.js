// /hooks/useUIStore.js
'use client';
import { create } from 'zustand';

const useUiStore = create((set) => ({
  hoveredFeature: null,
  addOnClickEnabled: false,

  // NEW
  solverEngine: 'ortools',            // 'ortools' | 'pyomo' | 'vroom'
  routingAdapter: 'haversine',        // 'haversine' | 'osm_graph' | 'openrouteservice'
  vrpType: 'TSP',                     // 'TSP' | 'CVRP' | 'VRPTW' | 'PDPTW'

  drawBBoxEnabled: false,
  lastBbox: null, // { minLon, minLat, maxLon, maxLat }

  trafficEnabled: false,
  setTrafficEnabled: (v) => set({ trafficEnabled: !!v }),

  tripsEnabled: false,
  setTripsEnabled: (v) => set({ tripsEnabled: !!v }),

  etasEnabled: false,
  etaEveryMeters: 600,
  etaSpeedKmh: 40,
  setEtasEnabled: (v) => set({ etasEnabled: !!v }),
  setEtaConfig: (p) => set(s => ({ ...s, ...p })),

  transformPreview: null,                // {coords, color?}
  setTransformPreview: (payload) => set({ transformPreview: payload }),
  clearTransformPreview: () => set({ transformPreview: null }),

  setSolverEngine: (v) => set({ solverEngine: v }),
  setRoutingAdapter: (v) => set({ routingAdapter: v }),
  setVrpType: (v) => set({ vrpType: v }),

  setHoveredFeature: (feature) => set({ hoveredFeature: feature }),
  clearHoveredFeature: () => set({ hoveredFeature: null }),
  toggleAddOnClick: () => set((s) => ({ addOnClickEnabled: !s.addOnClickEnabled })),

  setDrawBBoxEnabled: (val) => set({ drawBBoxEnabled: val }),
  setLastBbox: (bbox) => set({ lastBbox: bbox }),
  clearLastBbox: () => set({ lastBbox: null }),
}));

export default useUiStore;
