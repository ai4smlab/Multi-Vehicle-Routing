'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import Sidebar from '@/components/sidebar/Sidebar';

const DevExposeStores = dynamic(() => import('@/components/dev/DevExposeStores'), { ssr: false });
const MapboxComponent = dynamic(() => import('@/components/map/MapboxComponent'), { ssr: false });

export default function MapboxPage() {
  const sidebarRef = useRef(null);
  const [sidebarW, setSidebarW] = useState(320); // sensible default if Sidebar not measured yet

  useEffect(() => {
    if (!sidebarRef.current) return;
    const el = sidebarRef.current;

    // Watch the sidebar's box size (works for collapse/expand/drag-resize)
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const w = Math.round(entry.contentRect.width);
      setSidebarW(w);
      // publish CSS var so other components could use it too if needed
      document.documentElement.style.setProperty('--sidebar-w', `${w}px`);
    });

    ro.observe(el);
    // prime width once
    const rect = el.getBoundingClientRect();
    setSidebarW(Math.round(rect.width));
    document.documentElement.style.setProperty('--sidebar-w', `${Math.round(rect.width)}px`);

    return () => ro.disconnect();
  }, []);

  return (
    <div className="h-screen w-screen relative overflow-hidden">
      {/* Sidebar is positioned, measured by ResizeObserver */}
      <div ref={sidebarRef} className="absolute top-0 left-0 h-full z-20">
        <Sidebar />
      </div>

      {/* Map container starts right after the sidebar */}
      <div
        className="absolute top-0 right-0 h-full z-10"
        style={{ left: `var(--sidebar-w, ${sidebarW}px)` }} // fallback to state if var missing
      >
        {/* MapboxComponent uses absolute inset:0 internally, so this box defines its size */}
        <MapboxComponent />
        <DevExposeStores />
      </div>
    </div>
  );
}
