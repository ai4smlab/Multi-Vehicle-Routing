'use client';

import dynamic from 'next/dynamic';
import Sidebar from '@/components/sidebar/Sidebar';

const GoogleComponent = dynamic(() => import('@/components/map/GoogleComponent'), { ssr: false });

export default function GoogleMapsPage(){
  return (
    <div className="flex flex-row w-screen h-screen overflow-hidden">
      <Sidebar/>
      <div className="flex-1 relative">
        <GoogleComponent />
      </div>
    </div>
  );
}