'use client';
import Link from "next/link";
import { MapIcon, GlobeAltIcon, ServerIcon } from "@heroicons/react/24/outline";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-100 to-white dark:from-gray-900 dark:to-black text-gray-800 dark:text-gray-200 flex items-center justify-center p-6">
      <div className="max-w-xl w-full bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 space-y-6">
        <h1 className="text-2xl font-bold text-center">🗺️ Select Map Provider</h1>
        <p className="text-center text-gray-600 dark:text-gray-400">
          Choose a map rendering approach to explore routing and geospatial data:
        </p>

        <div className="grid sm:grid-cols-1 md:grid-cols-1 gap-4">
          <ProviderCard
            name="MapLibre GL JS"
            href="/map/maplibre"
            description="Open-source, client-side rendering with MapLibre."
            Icon={GlobeAltIcon}
          />
          <ProviderCard
            name="Mapbox GL JS"
            href="/map/mapbox"
            description="Mapbox-powered vector tile rendering (API key required)."
            Icon={MapIcon}
          />
          <ProviderCard
            name="Google Maps"
            href="/map/googlemaps"
            description="Standard provider for mapping (API key required)."
            Icon={GlobeAltIcon}
          />
        </div>
      </div>
    </main>
  );
}

function ProviderCard({ name, href, description, Icon }) {
  return (
    <Link href={href}>
      <div className="flex items-center gap-4 p-5 rounded-xl border border-slate-200 dark:border-slate-700 hover:shadow-md transition bg-slate-50 dark:bg-slate-700 hover:bg-slate-100 dark:hover:bg-slate-600 cursor-pointer">
        <Icon className="w-8 h-8 text-blue-600 dark:text-blue-400" />
        <div>
          <h2 className="text-lg font-semibold">{name}</h2>
          <p className="text-sm text-gray-600 dark:text-gray-400">{description}</p>
        </div>
      </div>
    </Link>
  );
}