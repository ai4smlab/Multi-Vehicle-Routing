// /hooks/useBackend.js
import { useQuery, useMutation } from '@tanstack/react-query';
import api from '@/api/api';

// ---- shared helpers / defaults ----
const DEFAULT_Q = {
  staleTime: 5 * 60 * 1000,        // 5 min: avoid thrashing on HMR or small UI changes
  refetchOnMount: false,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  retry: 1,
};

const keepPrev = { keepPreviousData: true };

function stableParamsKey(params) {
  if (!params) return '';
  // stable stringify: sort keys for deterministic key
  const keys = Object.keys(params).sort();
  return JSON.stringify(
    keys.reduce((o, k) => {
      const v = params[k];
      if (v === undefined) return o;
      o[k] = v;
      return o;
    }, {})
  );
}

/** GET /health */
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: async () => (await api.get('/health')).data,
    ...DEFAULT_Q,
  });
}

/** GET /status/adapters */
export function useStatusAdapters() {
  return useQuery({
    queryKey: ['statusAdapters'],
    queryFn: async () => (await api.get('/status/adapters')).data,
    ...DEFAULT_Q,
  });
}

/** GET /status/solvers */
export function useStatusSolvers() {
  return useQuery({
    queryKey: ['statusSolvers'],
    queryFn: async () => (await api.get('/status/solvers')).data,
    ...DEFAULT_Q,
  });
}

/** GET /capabilities  (unwraps {status,data}) */
export function useCapabilities() {
  return useQuery({
    queryKey: ['capabilities'],
    queryFn: async () => {
      const res = await api.get('/capabilities');
      return res.data?.data ?? res.data;
    },
    ...DEFAULT_Q,
  });
}

// GET /osm/pois/auto  (place search)
export function usePoisAuto(params) {
  return useQuery({
    queryKey: ['poisAuto', stableParamsKey(params)],
    queryFn: async () => (await api.get('/osm/pois/auto', { params })).data,
    enabled: !!params?.place,
    ...DEFAULT_Q, ...keepPrev,
  });
}

// GET /osm/pois  (bbox search: south,west,north,east)
export function usePois(params) {
  return useQuery({
    queryKey: ['pois', stableParamsKey(params)],
    queryFn: async () => (await api.get('/osm/pois', { params })).data,
    enabled: !!(params?.south && params?.west && params?.north && params?.east),
    ...DEFAULT_Q, ...keepPrev,
  });
}

/** GET /benchmarks */
export function useBenchmarks() {
  return useQuery({
    queryKey: ['benchmarks'],
    queryFn: async () => (await api.get('/benchmarks')).data,
    ...DEFAULT_Q,
  });
}

/** GET /benchmarks/files?dataset=...&q=...&limit=... */
export function useBenchmarkFiles(params) {
  return useQuery({
    queryKey: ['benchmarkFiles', stableParamsKey(params)],
    queryFn: async () => (await api.get('/benchmarks/files', { params })).data,
    enabled: !!params?.dataset,
    ...DEFAULT_Q, ...keepPrev,
  });
}

/** GET /benchmarks/load?dataset=...&name=...  (call-time params) */
export function useBenchmarkLoad() {
  return useMutation({
    mutationFn: async (params) =>
      (await api.get('/benchmarks/load', { params })).data,
  });
}

/** (optional) GET /benchmarks/find?dataset=...&name=... — to fetch best-known solution */
export async function fetchBenchmarkPair(dataset, name) {
  const { data } = await api.get('/benchmarks/find', { params: { dataset, name } });
  return data; // typically { instance: {...}, solution: {...} } or { pair: { solution: {...} } }
}

// --- FILES API ---

/** GET /files/datasets */
export function useFileDatasets() {
  return useQuery({
    queryKey: ['fileDatasets'],
    queryFn: async () => (await api.get('/files/datasets')).data,
    ...DEFAULT_Q,
  });
}

/** GET /files/list?dataset=...&cwd=...&q=...&exts=...&limit=...&offset=...&sort=...&order=... */
export function useFileList(params) {
  return useQuery({
    queryKey: ['fileList', stableParamsKey(params)],
    queryFn: async () => (await api.get('/files/list', { params })).data,
    enabled: !!params?.dataset, // don’t call until a dataset is chosen
    ...DEFAULT_Q, ...keepPrev,
  });
}

/** GET /files/find?dataset=...&q=...&exts=...&limit=...&offset=... */
export function useFileFind(params) {
  return useQuery({
    queryKey: ['fileFind', stableParamsKey(params)],
    queryFn: async () => (await api.get('/files/find', { params })).data,
    enabled: !!params?.dataset && !!params?.q,
    ...DEFAULT_Q, ...keepPrev,
  });
}

/** POST /files/upload  (multipart: file, subdir, overwrite) */
export function useFileUpload() {
  return useMutation({
    mutationFn: async ({ file, subdir, overwrite }) => {
      const fd = new FormData();
      fd.append('file', file);
      if (subdir) fd.append('subdir', subdir);
      if (typeof overwrite === 'boolean') fd.append('overwrite', String(overwrite));
      return (await api.post('/files/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })).data;
    },
  });
}

/** DELETE /files/delete?path=...  (NOTE: plural /files) */
export function useFileDelete() {
  return useMutation({
    mutationFn: async ({ path }) =>
      (await api.delete('/files/delete', { params: { path } })).data,
  });
}

/** POST /files/parse  { path, kind, options? } */
export function useFileParse() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/files/parse', payload)).data,
  });
}

/** POST /files/write/raw  { path, content, overwrite? } */
export function useFileWriteRaw() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/files/write/raw', payload)).data,
  });
}

/** POST /files/write/vrplib { path, waypoints, fleet, depot_index, matrix?, options? } */
export function useFileWriteVrplib() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/files/write/vrplib', payload)).data,
  });
}

/** POST /distance-matrix */
export function useDistanceMatrix() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/distance-matrix', payload)).data,
  });
}

/** POST /solver (synchronous) */
export function useSolve() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/solver', payload)).data,
  });
}

/** POST /emissions/estimate */
export function useEmissionsEstimate() {
  return useMutation({
    mutationFn: async (payload) => (await api.post('/emissions/estimate', payload)).data,
  });
}
