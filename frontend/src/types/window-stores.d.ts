// types/window-stores.d.ts
export {};

declare global {
  interface Window {
    // Zustand hooks (default exports)
    useWaypointStore: typeof import('@/hooks/useWaypointStore').default;
    useRouteStore: typeof import('@/hooks/useRouteStore').default;
    useMapStore: typeof import('@/hooks/useMapStore').default;

    // prefer this one
    useUiStore: typeof import('@/hooks/useUIStore').default;

    // legacy alias (if any code references it)
    useUIStore: typeof import('@/hooks/useUIStore').default;
  }
}
