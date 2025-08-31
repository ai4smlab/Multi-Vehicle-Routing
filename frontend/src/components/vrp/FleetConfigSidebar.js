'use client';

import { useEffect } from 'react';
import Section from '@/components/sidebar/Section';
import useFleetStore from '@/hooks/useFleetStore';

const VEHICLE_PRESETS = [
  {
    name: 'Van',
    capacity: 80,
    speed: 50,
    startTime: 6,
    endTime: 18,
    costPerDistance: 1,
    costPerTime: 0.5,
  },
  {
    name: 'Truck',
    capacity: 150,
    speed: 40,
    startTime: 5,
    endTime: 20,
    costPerDistance: 1.5,
    costPerTime: 0.8,
  },
  {
    name: 'Bike',
    capacity: 30,
    speed: 25,
    startTime: 8,
    endTime: 16,
    costPerDistance: 0.5,
    costPerTime: 0.2,
  }
];

export default function FleetConfigSidebar({ onChange }) {
    const {
        fleet,
        setFleet,
        addVehicle,
        removeVehicle,
    } = useFleetStore();
  

  useEffect(() => {
    onChange?.(fleet);
  }, [fleet, onChange]);

  const handleVehicleChange = (index, field, value) => {
    const updated = [...fleet];
    if (field === 'name') {
      updated[index][field] = value;
    } else {
      const num = parseFloat(value);
      updated[index][field] = isNaN(num) ? 0 : num;
    }
    setFleet(updated);
  };

  const applyPreset = (preset) => {
    const newVehicle = {
      id: Date.now(),
      ...preset,
    };
    setFleet([...fleet, newVehicle]);
  };

  return (
    <Section title="🚚 Fleet Configuration">
      {fleet.map((v, i) => {
        const isInvalidTimeWindow = v.startTime >= v.endTime;
        return (
          <Section key={v.id} title={`Vehicle ${i + 1}`} className="mb-4">
            <div className="mb-4 p-2 border rounded shadow-sm text-sm">
              <label className="block mb-1">
                Name:
                <input
                  type="text"
                  className="w-full p-1 border rounded"
                  value={v.name}
                  onChange={(e) => handleVehicleChange(i, 'name', e.target.value)}
                />
              </label>

              <label className="block mb-1">
                Capacity:
                <input
                  type="number"
                  min="0"
                  className="w-full p-1 border rounded"
                  value={v.capacity}
                  onChange={(e) => handleVehicleChange(i, 'capacity', e.target.value)}
                />
              </label>

              <label className="block mb-1">
                Speed (km/h):
                <input
                  type="number"
                  min="0"
                  className="w-full p-1 border rounded"
                  value={v.speed}
                  onChange={(e) => handleVehicleChange(i, 'speed', e.target.value)}
                />
              </label>

              <label className="block mb-1">
                Operating Time Window (Start - End):
                <div className="flex gap-2">
                  <input
                    type="number"
                    min="0"
                    className={`w-1/2 p-1 border rounded ${isInvalidTimeWindow ? 'border-red-500' : ''}`}
                    value={v.startTime}
                    onChange={(e) => handleVehicleChange(i, 'startTime', e.target.value)}
                  />
                  <input
                    type="number"
                    min="0"
                    className={`w-1/2 p-1 border rounded ${isInvalidTimeWindow ? 'border-red-500' : ''}`}
                    value={v.endTime}
                    onChange={(e) => handleVehicleChange(i, 'endTime', e.target.value)}
                  />
                </div>
                {isInvalidTimeWindow && (
                  <p className="text-xs text-red-500">Start time must be less than end time.</p>
                )}
              </label>

              <label className="block mb-1">
                Cost per Distance:
                <input
                  type="number"
                  min="0"
                  className="w-full p-1 border rounded"
                  value={v.costPerDistance}
                  onChange={(e) => handleVehicleChange(i, 'costPerDistance', e.target.value)}
                />
              </label>

              <label className="block mb-1">
                Cost per Time:
                <input
                  type="number"
                  min="0"
                  className="w-full p-1 border rounded"
                  value={v.costPerTime}
                  onChange={(e) => handleVehicleChange(i, 'costPerTime', e.target.value)}
                />
              </label>

              <button
                onClick={() => removeVehicle(i)}
                className="mt-2 text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Remove
              </button>
            </div>
          </Section>
        );
      })}

      <div className="mt-4 space-y-2">
        <button
          onClick={addVehicle}
          className="text-xs px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          ➕ Add Vehicle
        </button>

        <div>
          <label className="block text-xs mb-1">Presets:</label>
          <div className="flex flex-wrap gap-2">
            {VEHICLE_PRESETS.map((preset, idx) => (
              <button
                key={idx}
                onClick={() => applyPreset(preset)}
                className="text-xs px-2 py-1 bg-gray-500 text-white rounded hover:bg-gray-600"
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}
