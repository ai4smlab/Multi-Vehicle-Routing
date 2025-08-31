'use client';

import { useState } from "react";
import useWaypointStore from "@/hooks/useWaypointStore";
import Section from "../sidebar/Section";
import useUiStore from "@/hooks/useUIStore";
import useMapStore from "@/hooks/useMapStore"; // 👈 NEW

export default function WaypointSidebar() {
  const {
    waypoints,
    addWaypoint,
    resetWaypoints,
    removeWaypoint,
    moveWaypoint,
    toggleWaypointsVisible,
    waypointsVisible,
    setHoveredWaypoint,
    clearHoveredWaypoint,
    setWaypoints,
  } = useWaypointStore();

  const { addOnClickEnabled, toggleAddOnClick } = useUiStore();

  // 👇 NEW: camera control via shared map store
  const { viewState, setViewState } = useMapStore();

  const [newWaypoint, setNewWaypoint] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});

  // 👇 NEW: zoom helper
  const zoomToWaypoint = (wp, zoom = 16) => {
    const coords = wp?.coordinates;
    if (!Array.isArray(coords) || coords.length < 2) return;

    const [longitude, latitude] = coords;
    if (
      !Number.isFinite(longitude) || longitude < -180 || longitude > 180 ||
      !Number.isFinite(latitude) || latitude < -90 || latitude > 90
    ) return;

    // Preserve current bearing/pitch, set target zoom & center
    setViewState({
      longitude,
      latitude,
      zoom: Math.max(zoom, 2),
      bearing: viewState?.bearing ?? 0,
      pitch: viewState?.pitch ?? 0,
    });

    // Optional: briefly show the hover card at destination
    try {
      setHoveredWaypoint({ ...wp, position: coords });
      setTimeout(() => clearHoveredWaypoint(), 1200);
    } catch {}
  };

  const handleFieldChange = (index, field, value) => {
    const updated = [...waypoints];
    const errors = { ...fieldErrors };
    let isValid = true;

    const setError = (msg) => {
      errors[index] = { ...(errors[index] || {}), [field]: msg };
      isValid = false;
    };

    const clearError = () => {
      if (errors[index]) {
        delete errors[index][field];
        if (Object.keys(errors[index]).length === 0) delete errors[index];
      }
    };

    if (['demand', 'capacity', 'serviceTime'].includes(field)) {
      const num = parseFloat(value);
      if (isNaN(num) || num < 0) {
        setError("Must be ≥ 0");
      } else {
        updated[index][field] = num;
        clearError();
      }
    } else if (field === 'timeWindow') {
      const nums = value
        .split(',')
        .map(v => parseFloat(v.trim()))
        .filter(v => !isNaN(v));
      if (nums.length !== 2 || nums[0] >= nums[1]) {
        setError("Enter two numbers: start < end");
      } else {
        updated[index][field] = nums;
        clearError();
      }
    } else {
      updated[index][field] = value;
      clearError();
    }

    if (isValid) setWaypoints(updated);
    setFieldErrors(errors);
  };

  return (
    <Section title="🗺️ Waypoints">
      <div className="flex justify-between mb-2">
        <button
          onClick={resetWaypoints}
          className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Reset
        </button>
        <button
          onClick={toggleWaypointsVisible}
          className="text-xs px-2 py-1 bg-gray-600 text-white rounded hover:bg-gray-700"
        >
          {waypointsVisible ? "Hide" : "Show"}
        </button>
      </div>

      <div className="flex mb-2 space-x-2">
        <input
          type="text"
          value={newWaypoint}
          onChange={(e) => {
            const val = e.target.value;
            // Only allow digits, commas, dot, minus sign, and spaces
            if (/^[\d\s.,-]*$/.test(val)) {
              setNewWaypoint(val);
            }
          }}
          placeholder="Lng,Lat"
          className="w-full px-2 py-1 border rounded text-sm dark:bg-gray-700 dark:text-white"
        />
        <button
          onClick={() => {
            const parts = newWaypoint.split(",").map(Number);
            if (
              parts.length === 2 &&
              parts.every((n) => !isNaN(n)) &&
              parts[0] >= -180 && parts[0] <= 180 &&
              parts[1] >= -90 && parts[1] <= 90
            ) {
              const wp = {
                coordinates: parts,
                id: Date.now(),
                demand: 1,
                capacity: 5,
                serviceTime: 10,
                timeWindow: [8, 17],
              };
              addWaypoint(wp);
              setNewWaypoint("");
              // optional: auto-zoom to newly added point
              zoomToWaypoint(wp, 16);
            } else {
              alert("Invalid coordinates: use format Lng,Lat in valid range.");
            }
          }}
          className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
        >
          Add
        </button>
      </div>

      <ul className="space-y-2 text-sm max-h-96 overflow-y-auto">
        {Array.isArray(waypoints) && waypoints.map((wp, index) => (
          <li
            key={wp.id ?? index}
            className={`border rounded p-2 shadow-sm hover:bg-gray-100 dark:hover:bg-gray-800
              ${wp.type === 'Depot' ? 'border-blue-500' :
                wp.type === 'Delivery' ? 'border-green-500' :
                wp.type === 'Pickup' ? 'border-yellow-500' :
                wp.type === 'Backhaul' ? 'border-red-500' :
                'border-gray-300'
              }`}
            onMouseEnter={() => setHoveredWaypoint(wp)}
            onMouseLeave={() => clearHoveredWaypoint()}
          >
            <Section title={`Waypoint #${index + 1}`}>
              <label className="block mb-1">
                Type:
                <select
                  className="w-full p-1 border rounded"
                  value={wp.type || (index === 0 ? 'Depot' : 'customer')}
                  onChange={(e) => handleFieldChange(index, 'type', e.target.value)}
                >
                  <option value="Depot">Depot</option>
                  <option value="Delivery">Delivery</option>
                  <option value="Pickup">Pickup</option>
                  <option value="Backhaul">Backhaul</option>
                </select>
              </label>

              <label className="block mb-1">
                Demand:
                <input
                  type="number"
                  className="w-full p-1 border rounded"
                  value={wp.demand ?? ''}
                  onChange={(e) => handleFieldChange(index, 'demand', e.target.value)}
                />
                {fieldErrors[index]?.demand && (
                  <p className="text-xs text-red-500">{fieldErrors[index].demand}</p>
                )}
              </label>

              <label className="block mb-1">
                Capacity:
                <input
                  type="number"
                  className="w-full p-1 border rounded"
                  value={wp.capacity ?? ''}
                  onChange={(e) => handleFieldChange(index, 'capacity', e.target.value)}
                />
                {fieldErrors[index]?.capacity && (
                  <p className="text-xs text-red-500">{fieldErrors[index].capacity}</p>
                )}
              </label>

              <label className="block mb-1">
                Service Time:
                <input
                  type="number"
                  className="w-full p-1 border rounded"
                  value={wp.serviceTime ?? ''}
                  onChange={(e) => handleFieldChange(index, 'serviceTime', e.target.value)}
                />
                {fieldErrors[index]?.serviceTime && (
                  <p className="text-xs text-red-500">{fieldErrors[index].serviceTime}</p>
                )}
              </label>

              <label className="block mb-1">
                Time Window (comma-separated):
                <input
                  type="text"
                  className="w-full p-1 border rounded"
                  placeholder="e.g. 8,17"
                  value={
                    Array.isArray(wp.timeWindow)
                      ? wp.timeWindow.join(',')
                      : typeof wp.timeWindow === 'string'
                        ? wp.timeWindow
                        : ''
                  }
                  onChange={(e) => {
                    const input = e.target.value;
                    const sanitized = input.replace(/[^0-9,\s]/g, '');
                    const parsed = sanitized
                      .split(',')
                      .map(v => parseFloat(v.trim()))
                      .filter(v => !isNaN(v));

                    handleFieldChange(index, 'timeWindow', sanitized); // store raw string for display
                    if (parsed.length === 2) {
                      handleFieldChange(index, 'timeWindow', parsed);
                    }
                  }}
                />
                {fieldErrors[index]?.timeWindow && (
                  <p className="text-xs text-red-500">{fieldErrors[index].timeWindow}</p>
                )}
              </label>

              <label className="block mb-1">
                Pair ID:
                <input
                  type="text"
                  className="w-full p-1 border rounded"
                  value={wp.pairId ?? ''}
                  onChange={(e) => handleFieldChange(index, 'pairId', e.target.value)}
                />
              </label>
            </Section>

            <div className="flex justify-end space-x-1 mt-2">
              {/* 👇 NEW: Zoom button */}
              <button
                onClick={() => zoomToWaypoint(wp, 16)}
                className="text-xs px-2 py-0.5 bg-emerald-600 text-white rounded hover:bg-emerald-700"
                title="Zoom to waypoint"
              >
                🔎
              </button>

              <button
                onClick={() => moveWaypoint(index, -1)}
                className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600"
                disabled={index === 0}
              >
                ↑
              </button>
              <button
                onClick={() => moveWaypoint(index, 1)}
                className="text-xs px-2 py-0.5 bg-blue-500 text-white rounded hover:bg-blue-600"
                disabled={index === waypoints.length - 1}
              >
                ↓
              </button>
              <button
                onClick={() => removeWaypoint(index)}
                className="text-xs px-2 py-0.5 bg-red-500 text-white rounded hover:bg-red-600"
              >
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>

      <div className="flex justify-between mt-4">
        <button
          onClick={toggleAddOnClick}
          className={`text-xs px-2 py-1 rounded ${addOnClickEnabled ? "bg-green-600 hover:bg-green-700" : "bg-gray-600 hover:bg-gray-700"} text-white`}
        >
          {addOnClickEnabled ? "🖱️ Click-to-Add: On" : "🖱️ Click-to-Add: Off"}
        </button>
      </div>
    </Section>
  );
}
