// components/dev/DevExposeStores.tsx
'use client';
import { useEffect } from 'react';
import useWaypointStore from '@/hooks/useWaypointStore';
import useRouteStore from '@/hooks/useRouteStore';
//import useMapStore from '@/hooks/useMapStore';
import useUiStore from '@/hooks/useUIStore';

export default function DevExposeStores() {
  useEffect(() => {
    // primary (recommended) names
    (window as any).useWaypointStore = useWaypointStore;
    (window as any).useRouteStore = useRouteStore;
    //(window as any).useMapStore = useMapStore;
    (window as any).useUiStore = useUiStore;

    // backward-compat alias (capital-I version if any code still references it)
    (window as any).useUIStore = useUiStore;

    console.debug('[dev] Exposed stores on window: useWaypointStore, useRouteStore, useMapStore, useUiStore');
  }, []);
  return null;
}
