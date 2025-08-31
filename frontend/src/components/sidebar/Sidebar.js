'use client';
import { useState } from "react";
import { ChevronLeftIcon, ChevronRightIcon } from "@heroicons/react/24/solid";
import Section from "@/components/sidebar/Section";
import useWaypointStore from "@/hooks/useWaypointStore";
import WaypointSidebar from "@/components/vrp/WaypointSidebar";
import FleetConfigSidebar from "@/components/vrp/FleetConfigSidebar";
import SidebarSearchBox from "@/components/sidebar/SidebarSearchBox";
import BenchmarkSelector from "@/components/datasets/BenchmarkSelector";
import RealWorldDatasetPanel from "@/components/datasets/RealWorldDatasetPanel";
import CustomDatasetPanel from "@/components/data/CustomDatasetPanel";
import ResultSummaryPanel from "@/components/vrp/ResultSummaryPanel";
import DataManagerPanel from "@/components/datasets/DataManagerPanel";
import WeightTunerPanel from "@/components/vrp/WeightTunerPanel";
import SolverPanel from "@/components/vrp/SolverPanel";
import RouteToolsPanel from '@/components/sidebar/RouteToolsPanel';

const API_KEY = process.env.NEXT_PUBLIC_LOCATIONIQ_API_KEY;

export default function Sidebar({ }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const {
    addWaypoint,
  } = useWaypointStore();

  return (
    <div
      className={`absolute top-0 left-0 h-full bg-white dark:bg-gray-800 border-r dark:border-gray-700 shadow-lg z-20 transition-all duration-300 ease-in-out ${sidebarOpen ? "w-72" : "w-12"
        }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b dark:border-gray-600">
        <h2
          className={`text-sm font-semibold text-gray-800 dark:text-white transition-opacity duration-300 ${sidebarOpen ? "opacity-100" : "opacity-0 w-0 overflow-hidden"
            }`}
        >
          Controls
        </h2>
        <button
          className="text-gray-600 dark:text-gray-300 hover:text-black dark:hover:text-white transition"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          {sidebarOpen ? (
            <ChevronLeftIcon className="h-5 w-5" />
          ) : (
            <ChevronRightIcon className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* Content */}
      <div
        className={`overflow-y-auto h-[calc(100%-3rem)] px-4 py-4 space-y-6 transition-opacity duration-300 ${sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
      >
        {/* 🔍 Search Section */}
        <Section title="🔍 Search Location">
          <SidebarSearchBox apiKey={API_KEY} onWaypoint={addWaypoint} />
        </Section>

        {/* 📂 Data Manager */}
        <DataManagerPanel />

        {/* 🚚 Route Planner  */}
        <Section title="🚚 Route Planner">
          {/* 🚚 Fleet */}
          <FleetConfigSidebar />
          {/* 🗺️ Waypoints */}
          <WaypointSidebar />
          {/* 🧠 Solver */}
          <SolverPanel />
        </Section>

        {/* 📤 Benchmark Selector */}
        <BenchmarkSelector
          fetchBenchmarks={async () => {
            // Simulated API call – replace with real fetch
            return {
              types: ['Solomon', 'CVRPLIB'],
              data: {
                Solomon: ['c101.txt', 'r101.txt', 'rc101.txt', 'r201.txt'],
                CVRPLIB: ['A-n32-k5.vrp', 'B-n50-k7.vrp']
              }
            };
          }}
          onSelect={(type, name) => {
            console.log('Selected:', type, name);
            // You could trigger load into map or solver next
          }}
        />

        {/* 📤 Real-World Dataset */}
        <RealWorldDatasetPanel />

        {/* 📤 Custom Datasets (Server) */}
        <Section title="📤 Custom Datasets (Server)">
          <CustomDatasetPanel />
        </Section>

        {/* 📤 Weight Panel */}
        <WeightTunerPanel />

        {/* 📤 Route Tools */}
        <RouteToolsPanel />
        {/* 📊 Summary */}
        <ResultSummaryPanel />
      </div>
    </div>
  );
}
