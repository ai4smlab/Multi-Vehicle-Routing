'use client';

import { useState } from 'react';
import Section from '@/components/sidebar/Section';
import detectComplexityTraits from '@/components/vrp/detectComplexityTraits';
import detectRegionTraits from '@/components/vrp/detectRegionTraits';
import AutoSuggestWeights from '@/components/vrp/autoSuggestWeights';

export default function WeightTunerPanel({ onChange }) {
    const [weights, setWeights] = useState({
        cost: 0.25,
        time: 0.25,
        emissions: 0.25,
        distance: 0.15,
        reliability: 0.10,
    });

    const [explanations, setExplanations] = useState([]);
    const [autoBalance, setAutoBalance] = useState(true);
    const [locked, setLocked] = useState({
        cost: false,
        time: false,
        emissions: false,
        distance: false,
        reliability: false,
    });
    const toggleLock = (key) => {
        setLocked(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const PRESETS = {
        costFocused: {
            label: "Minimize Cost",
            weights: {
                cost: 0.5,
                time: 0.2,
                emissions: 0.1,
                distance: 0.15,
                reliability: 0.05,
            },
        },
        timeSensitive: {
            label: "Time-Sensitive",
            weights: {
                cost: 0.1,
                time: 0.4,
                emissions: 0.1,
                distance: 0.2,
                reliability: 0.2,
            },
        },
        ecoFriendly: {
            label: "Eco-Friendly",
            weights: {
                cost: 0.1,
                time: 0.15,
                emissions: 0.4,
                distance: 0.25,
                reliability: 0.1,
            },
        },
    };


    const round2 = (n) => Math.round(n * 100) / 100;

    const handleWeightChange = (key, newValue) => {
        if (locked[key]) return;
        // Clamp and round to two decimals
        newValue = round2(Math.max(0, Math.min(1, newValue)));

        let newWeights = { ...weights, [key]: newValue };

        if (autoBalance) {
            const total = Object.values(newWeights).reduce((a, b) => a + b, 0);
            const roundedTotal = round2(total);

            if (roundedTotal > 1.0) {
                // Amount to reduce
                let overflow = round2(roundedTotal - 1.0);

                const adjustableKeys = Object.keys(newWeights).filter(
                    k => k !== key && !locked[k] && newWeights[k] > 0
                );

                const totalAdjustable = adjustableKeys.reduce((sum, k) => sum + newWeights[k], 0);

                if (totalAdjustable > 0) {
                    // 🔁 Spread the overflow across other unlocked weights
                    for (const k of adjustableKeys) {
                        const share = newWeights[k] / totalAdjustable;
                        const reduction = round2(overflow * share);
                        newWeights[k] = round2(Math.max(0, newWeights[k] - reduction));
                    }
                } else {
                    // ❗ No other keys can be reduced → clamp the edited value itself
                    newWeights[key] = round2(Math.max(0, newWeights[key] - overflow));
                }
            }

            // Final rounding correction (up to 0.01 off)
            const finalTotal = Object.values(newWeights).reduce((sum, val) => sum + val, 0);
            const error = round2(1.0 - finalTotal);

            if (Math.abs(error) >= 0.01) {
                const candidates = Object.entries(newWeights)
                    .filter(([k]) => k !== key && !locked[k])
                    .sort((a, b) => b[1] - a[1]);

                if (candidates.length > 0) {
                    const [targetKey, val] = candidates[0];
                    newWeights[targetKey] = round2(Math.max(0, val + error));
                }
            }
        }

        setWeights(newWeights);
        onChange?.(newWeights);
    };

    const total = Object.values(weights).reduce((sum, val) => sum + val, 0);

    // 🚀 Auto-fill from complexity
    const applyComplexity = () => {
        const { weights: newWeights, explanation } = detectComplexityTraits(waypoints);
        setWeights(newWeights);
        setExplanations(explanation);
        onChange?.(newWeights);
    };

    // 🌍 Auto-fill from region
    const applyRegion = () => {
        const { weights: newWeights, explanation } = detectRegionTraits(region);
        setWeights(newWeights);
        setExplanations(explanation);
        onChange?.(newWeights);
    };

    return (
        <Section title="🎯 VRP Factor Weights">
            {Object.entries(weights).map(([key, value]) => (
                <div key={key} className="mb-2">
                    <label className="block text-sm font-medium capitalize">
                        {key}
                        <button
                            type="button"
                            onClick={() => toggleLock(key)}
                            className="text-ms ml-2"
                        >
                            {locked[key] ? '🔒 Locked' : '🔓 Unlock'}
                        </button>
                    </label>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={value}
                        onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                        disabled={locked[key]}
                        className="w-full border p-1 rounded text-base"
                    />
                    <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.01"
                        value={value}
                        onChange={(e) => handleWeightChange(key, parseFloat(e.target.value))}
                        disabled={locked[key]}
                        className="w-16 text-sm border p-1 rounded"
                    />
                    <span className="text-sm"></span>
                </div>
            ))}

            <div className="mt-2 font-medium">
                Total: {round2(total).toFixed(2)}
                {round2(total) !== 1.00 && (
                    <span className="text-red-600 ml-2">⚠️ Must total 1.00</span>
                )}
            </div>
            <div className="flex items-center space-x-2 text-sm mb-2">
                <label>
                    <input
                        type="checkbox"
                        checked={autoBalance}
                        onChange={() => setAutoBalance(!autoBalance)}
                        className="mr-1"
                    />
                    Auto-balance weights
                </label>
            </div>
            <div className="mt-2 space-y-2">
                <div className="font-medium text-sm">🎛 Presets:</div>
                <div className="flex flex-wrap gap-2">
                    {Object.entries(PRESETS).map(([key, { label, weights: presetWeights }]) => (
                        <button
                            key={key}
                            onClick={() => {
                                setWeights(presetWeights);
                                setExplanations([`Applied preset: ${label}`]);
                            }}
                            className="text-xs text-gray-800 px-2 py-1 bg-gray-200 hover:bg-gray-300 rounded"
                        >
                            {label}
                        </button>
                    ))}
                </div>
            </div>
            <div className="mt-4 space-y-2">
                <div className="flex flex-wrap gap-2 text-xs">
                    <button onClick={applyComplexity} className="bg-blue-100 text-black px-2 py-1 rounded">
                        📈 Detect Complexity
                    </button>
                    <button onClick={applyRegion} className="bg-emerald-100 text-black px-2 py-1 rounded">
                        🗺️ Detect Region
                    </button>
                </div>
            </div>
            <div className="mt-1 space-y-1">
                <AutoSuggestWeights
                    onSuggest={(suggestedWeights, reasons) => {
                        setWeights(suggestedWeights);
                        setExplanations(reasons);
                        onChange?.(suggestedWeights);
                    }}
                />
            </div>
            {explanations.length > 0 && (
                <div className="mt-2 bg-black-50 text-sm border p-2 rounded">
                    <div className="font-semibold mb-1">Why these weights?</div>
                    <ul className="list-disc list-inside space-y-1">
                        {explanations.map((ex, i) => <li key={i}>{ex}</li>)}
                    </ul>
                </div>
            )}
        </Section>
    );
}