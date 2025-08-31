'use client';

import { useMemo, useState } from 'react';
import Section from '@/components/sidebar/Section';
import useVrpStore from '@/hooks/useVRPStore';
import FileUpload from '@/components/data/FileUpload';
import useWaypointStore from '@/hooks/useWaypointStore';
import useFleetStore from '@/hooks/useFleetStore';
import {
    waypointsToFeatures,
    vehiclesToFeatures,
    collectAllFeatures,
    downloadAsGeoJSON
} from '@/utils/geojsonExport';
import fitToFeatures from '@/components/map/fitToFeatures';
import useMapStore from '@/hooks/useMapStore';

/**
 * Tagging Truth Table (no duplication / idempotent)
 *
 * Given features have `properties.tags` as array (unique):
 *
 * 1) Tag only
 *    - before: []          + add "A" → ["A"]
 * 2) Re-tag same selection
 *    - before: ["A"]       + add "A" → ["A"]            (no duplicates)
 * 3) Assign new tag and remove previous
 *    - before: ["A"]       + replace "A"→"B" → ["B"]
 * 4) Bulk tag remove
 *    - before: ["A","B"]   + remove "A" → ["B"]
 * 5) Mixed file IDs
 *    - only fileId matches are updated
 *
 * See helper `applyTagOperationToFileFeatures` and the inline quick-test at bottom.
 */

function uniquePush(arr, v) {
    const s = new Set(arr || []);
    s.add(v);
    return [...s];
}
function removeFrom(arr, v) {
    return (arr || []).filter(x => x !== v);
}

function applyTagOperationToFileFeatures(file, op) {
    if (!file?.data?.features?.length) return file;
    const nextFeatures = file.data.features.map((f) => {
        const p = { ...(f.properties || {}) };
        const tags = Array.isArray(p.tags) ? p.tags.slice() : [];
        if (op.type === 'add') {
            p.tags = uniquePush(tags, op.tag);
        } else if (op.type === 'remove') {
            p.tags = removeFrom(tags, op.tag);
        } else if (op.type === 'replace') {
            p.tags = uniquePush(removeFrom(tags, op.from), op.to);
        }
        return { ...f, properties: p };
    });
    return { ...file, data: { ...file.data, features: nextFeatures } };
}

export default function DataManagerPanel() {
    const {
        GeojsonFiles,
        removeGeojsonFile,
        // setGeojsonFiles, // not required; we'll update via getState/ setState to avoid render-time mutation
        toggleFileVisibility,
        addGeojsonFile
    } = useVrpStore();

    const [exportType, setExportType] = useState('waypoints');
    const removeWaypointsByFileId = useWaypointStore((s) => s.removeWaypointsByFileId);
    const [importOptions, setImportOptions] = useState({
        autodetect: true,
        skipDuplicates: true,
        tagUntagged: true,
    });

    const waypoints = useWaypointStore((s) => s.waypoints);
    const vehicles = (typeof useFleetStore === 'function'
        ? useFleetStore((s) => s.vehicles)
        : []);

    const toFeatureCollection = (file) => {
        if (!file) return null;
        if (file?.data?.type === 'FeatureCollection') return file.data;
        const features = file?.data?.features ?? file?.features ?? [];
        return { type: 'FeatureCollection', features };
    };

    const handleExport = () => {
        const files = useVrpStore.getState().GeojsonFiles;

        const wpFeatures = waypointsToFeatures(waypoints);
        const vehFeatures = vehiclesToFeatures(vehicles);

        const all = collectAllFeatures({
            importedFiles: files,
            waypointFeatures: wpFeatures,
            vehicleFeatures: vehFeatures,
        });

        let featuresToExport = all;
        if (exportType === 'waypoints') {
            featuresToExport = all.filter((f) => f?.properties?._featureType === 'waypoint');
        } else if (exportType === 'vehicles') {
            featuresToExport = all.filter((f) => f?.properties?._featureType === 'vehicle');
        } else if (exportType === 'layers') {
            featuresToExport = all.filter(
                (f) =>
                    f?.properties?._featureType !== 'waypoint' &&
                    f?.properties?._featureType !== 'vehicle'
            );
        }

        downloadAsGeoJSON(`${exportType}-export.geojson`, featuresToExport);
    };

    const handleRemove = (fileId) => {
        console.debug('[DataMgr] remove file', fileId);
        removeGeojsonFile(fileId);
        removeWaypointsByFileId(fileId);
    };

    // Simple tagging UI (applies to one file at a time)
    const [tagTargetFileId, setTagTargetFileId] = useState('');
    const [tagInput, setTagInput] = useState('');
    const [replaceFrom, setReplaceFrom] = useState('');
    const [replaceTo, setReplaceTo] = useState('');

    const selectedFile = useMemo(
        () => GeojsonFiles.find(f => String(f.id) === String(tagTargetFileId)) || null,
        [GeojsonFiles, tagTargetFileId]
    );

    const runTagOp = (op) => {
        if (!selectedFile) return;
        queueMicrotask(() => {
            // mutate via setState to avoid render-time updates
            useVrpStore.setState((s) => {
                const list = s.GeojsonFiles.map((f) =>
                    String(f.id) === String(selectedFile.id) ? applyTagOperationToFileFeatures(f, op) : f
                );
                return { GeojsonFiles: list };
            });
            console.debug('[DataMgr] tag op', op);
        });
    };

    // Quick zoom helper
    const setViewState = useMapStore(s => s.setViewState);
    const zoomTo = (file) => {
        const fc = toFeatureCollection(file);
        if (!fc?.features?.length) return;
        fitToFeatures(fc.features, { setViewState });
    };

    return (
        <Section title="📁 Data Manager (Local)">
            <Section title="⬆️ Import Options">
                <div className="text-xs space-y-1">
                    <label>
                        <input
                            type="checkbox"
                            checked={importOptions.autodetect}
                            onChange={(e) =>
                                setImportOptions((o) => ({ ...o, autodetect: e.target.checked }))
                            }
                        />{' '}
                        Autodetect type
                    </label>
                    <br />
                    <label>
                        <input
                            type="checkbox"
                            checked={importOptions.skipDuplicates}
                            onChange={(e) =>
                                setImportOptions((o) => ({ ...o, skipDuplicates: e.target.checked }))
                            }
                        />{' '}
                        Skip duplicates
                    </label>
                    <br />
                    <label>
                        <input
                            type="checkbox"
                            checked={importOptions.tagUntagged}
                            onChange={(e) =>
                                setImportOptions((o) => ({ ...o, tagUntagged: e.target.checked }))
                            }
                        />{' '}
                        Tag untagged features as map
                    </label>
                </div>
            </Section>

            <Section title="📂 Imported Files">
                <FileUpload importOptions={importOptions} />

                {GeojsonFiles.length === 0 ? (
                    <div className="text-xs text-gray-500">No imported files yet.</div>
                ) : (
                    GeojsonFiles.map((file) => (
                        <div key={file.id} className="p-2 border rounded mb-1">
                            <div className="font-medium text-sm">{file.name}</div>

                            <div className="flex gap-2 text-xs text-gray-600 mt-1">
                                {(file.fileTypes ?? ['unknown']).map((type, i) => (
                                    <span
                                        key={i}
                                        className={`px-2 py-0.5 rounded 
                      ${type === 'waypoint'
                                                ? 'bg-emerald-100 text-emerald-800'
                                                : type === 'vehicle'
                                                    ? 'bg-blue-100 text-blue-800'
                                                    : type === 'map'
                                                        ? 'bg-yellow-100 text-yellow-800'
                                                        : 'bg-gray-100 text-gray-800'
                                            }`}
                                    >
                                        {type}
                                    </span>
                                ))}
                            </div>

                            <div className="flex flex-wrap gap-2 mt-2 text-sm">
                                <button onClick={() => toggleFileVisibility(file.id)}>
                                    👁 {file.visible ? 'Hide' : 'Show'}
                                </button>
                                <button onClick={() => handleRemove(file.id)}>🗑 Remove</button>
                                <button
                                    onClick={() => zoomTo(file)}
                                >
                                    🎯 Zoom
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </Section>

            {/* Tagging demo (immutable, deduped) */}
            <Section title="🏷️ Tagging (no-dup demo)">
                <div className="grid grid-cols-1 gap-2 text-xs">
                    <div className="flex gap-2 items-center">
                        <span>File:</span>
                        <select
                            className="border rounded p-1"
                            value={tagTargetFileId}
                            onChange={(e) => setTagTargetFileId(e.target.value)}
                        >
                            <option value="">— select file —</option>
                            {GeojsonFiles.map(f => <option key={f.id} value={String(f.id)}>{f.name}</option>)}
                        </select>
                    </div>
                    <div className="flex gap-2 items-center">
                        <input
                            className="border rounded p-1"
                            placeholder='tag e.g. "restaurant"'
                            value={tagInput}
                            onChange={(e) => setTagInput(e.target.value)}
                        />
                        <button
                            className="px-2 py-1 bg-emerald-600 text-white rounded disabled:opacity-50"
                            disabled={!selectedFile || !tagInput}
                            onClick={() => runTagOp({ type: 'add', tag: tagInput })}
                        >
                            Add tag
                        </button>
                        <button
                            className="px-2 py-1 bg-rose-600 text-white rounded disabled:opacity-50"
                            disabled={!selectedFile || !tagInput}
                            onClick={() => runTagOp({ type: 'remove', tag: tagInput })}
                        >
                            Remove tag
                        </button>
                    </div>

                    <div className="flex gap-2 items-center">
                        <input
                            className="border rounded p-1"
                            placeholder='from tag'
                            value={replaceFrom}
                            onChange={(e) => setReplaceFrom(e.target.value)}
                        />
                        <input
                            className="border rounded p-1"
                            placeholder='to tag'
                            value={replaceTo}
                            onChange={(e) => setReplaceTo(e.target.value)}
                        />
                        <button
                            className="px-2 py-1 bg-indigo-600 text-white rounded disabled:opacity-50"
                            disabled={!selectedFile || !replaceFrom || !replaceTo}
                            onClick={() => runTagOp({ type: 'replace', from: replaceFrom, to: replaceTo })}
                        >
                            Replace tag
                        </button>
                    </div>
                </div>
                {/* Quick test util in console:
           window.__DataMgrTest && window.__DataMgrTest()
        */}
            </Section>

            <Section title="⬇️ Export">
                <select
                    value={exportType}
                    onChange={(e) => setExportType(e.target.value)}
                    className="w-full p-1 text-sm border rounded mb-2"
                >
                    <option value="waypoints">Waypoints</option>
                    <option value="layers">Map Layers</option>
                    <option value="vehicles">Vehicles</option>
                    <option value="all">Full Dataset</option>
                </select>

                <button
                    onClick={handleExport}
                    className="text-xs px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700"
                >
                    💾 Export Selected
                </button>
            </Section>
        </Section>
    );
}

// Expose a tiny manual test helper if needed (runs in console)
if (typeof window !== 'undefined') {
    window.__DataMgrTest = function () {
        const s = useVrpStore.getState();
        const first = s.GeojsonFiles[0];
        if (!first) { console.warn('[DataMgr] no files'); return; }
        const before = first?.data?.features?.[0]?.properties?.tags || [];
        console.log('[DataMgr] before', before);
        useVrpStore.setState(state => {
            const list = state.GeojsonFiles.map((f) =>
                f.id === first.id ? applyTagOperationToFileFeatures(f, { type: 'add', tag: 'A' }) : f
            );
            return { GeojsonFiles: list };
        });
        const after = useVrpStore.getState().GeojsonFiles[0]?.data?.features?.[0]?.properties?.tags || [];
        console.log('[DataMgr] after add A', after);
    };
}
