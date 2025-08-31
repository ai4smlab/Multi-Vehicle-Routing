import { useCallback } from 'react';
import detectRegionTraits from '@/components/vrp/detectRegionTraits';
import detectComplexityTraits from '@/components/vrp/detectComplexityTraits';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';

export default function autoSuggestWeights({ onSuggest }) {
    const waypoints = useWaypointStore((s) => s.waypoints);
    const vehicleCount = useFleetStore((s) => s.fleet.length);

    const handleClick = useCallback(() => {
        if (waypoints.length === 0 || vehicleCount === 0) {
            alert("Please add waypoints and configure vehicles first.");
            return;
        }

        const coords = waypoints.map(wp => wp.coordinates);
        const regionTraits = detectRegionTraits(coords);
        const complexityTraits = detectComplexityTraits(waypoints, vehicleCount);

        const weights = {
            distance: regionTraits.isRural ? 0.35 : 0.15,
            time: regionTraits.isUrban ? 0.35 : 0.15,
            cost: complexityTraits.hasHighDemand ? 0.20 : 0.10,
            emissions: regionTraits.hasHillyTerrain ? 0.20 : 0.10,
            reliability: complexityTraits.hasTightWindows ? 0.15 : 0.05,
        };

        // Normalize weights to total 1.0
        const total = Object.values(weights).reduce((a, b) => a + b, 0);
        Object.keys(weights).forEach(k => {
            weights[k] = +(weights[k] / total).toFixed(2);
        });

        const reasons = [];

        if (regionTraits.isUrban) reasons.push("Increased time weight due to urban conditions.");
        if (regionTraits.isRural) reasons.push("Increased distance weight due to rural spacing.");
        if (regionTraits.hasHillyTerrain) reasons.push("Emissions weight raised due to terrain difficulty.");
        if (complexityTraits.hasHighDemand) reasons.push("Cost weight increased due to high demand.");
        if (complexityTraits.hasTightWindows) reasons.push("Reliability weight raised due to tight time windows.");

        onSuggest?.(weights, reasons);
    }, [waypoints, vehicleCount, onSuggest]);

    return (
        <button
            onClick={handleClick}
            className="text-sm px-3 py-1 bg-amber-600 text-white rounded hover:bg-amber-700 mt-2"
        >
            ⚡ Auto-Suggest Weights
        </button>
    );
}
