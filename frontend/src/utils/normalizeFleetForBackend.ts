// Unified helpers + both return shapes

export type VehicleIn = {
  id?: string | number;
  capacity?: number | number[];
  start?: number;
  end?: number;
  time_window?: [number | string, number | string];
  speed?: number;
  emissions_per_km?: number;
  [k: string]: any;
};

export type VehicleOut = {
  id: string;
  capacity: number[];
  start: number;
  end: number;
  time_window?: [number, number];
  speed?: number;
  emissions_per_km?: number;
  [k: string]: any;
};

// ---- core: always returns an array (what Vitest expects as default import)
export function toFleetArray(vehicles?: VehicleIn[] | null): VehicleOut[] {
  if (!Array.isArray(vehicles) || vehicles.length === 0) return [];

  return vehicles.map((v, idx) => {
    const id = v?.id ?? `veh-${idx + 1}`;

    const capacityArr = Array.isArray(v?.capacity)
      ? v.capacity.map(x => Number(x ?? 0))
      : v?.capacity != null
        ? [Number(v.capacity)]
        : [0];

    const start = Number.isFinite(v?.start) ? Number(v!.start) : 0;
    const end   = Number.isFinite(v?.end)   ? Number(v!.end)   : 0;

    let time_window: [number, number] | undefined;
    if (Array.isArray(v?.time_window) && v!.time_window.length === 2) {
      time_window = [Number(v!.time_window[0]), Number(v!.time_window[1])];
    }

    const speed = Number.isFinite(v?.speed) ? Number(v!.speed) : undefined;
    const emissions_per_km = Number.isFinite(v?.emissions_per_km)
      ? Number(v!.emissions_per_km)
      : undefined;

    const { id: _i, capacity: _c, start: _s, end: _e, time_window: _tw, ...rest } = v ?? {};

    return {
      id: String(id),
      capacity: capacityArr,
      start,
      end,
      ...(time_window ? { time_window } : {}),
      ...(speed != null ? { speed } : {}),
      ...(emissions_per_km != null ? { emissions_per_km } : {}),
      ...rest,
    };
  });
}

// ---- compatibility wrapper: accepts array or {vehicles} and returns { vehicles: [...] }
// (matches your app’s previous JS usage)
export function normalizeFleetForBackend(
  frontendFleet: VehicleIn[] | { vehicles?: VehicleIn[] } = [],
  { defaultStart = 0, defaultEnd = 0 }: { defaultStart?: number; defaultEnd?: number } = {}
): { vehicles: VehicleOut[] } {
  const vehiclesArray = Array.isArray(frontendFleet)
    ? frontendFleet
    : Array.isArray((frontendFleet as any)?.vehicles)
      ? (frontendFleet as any).vehicles
      : [];

  const arr = toFleetArray(vehiclesArray).map(v => ({
    ...v,
    start: Number.isFinite(v.start) ? v.start : defaultStart,
    end: Number.isFinite(v.end) ? v.end : defaultEnd,
  }));

  return { vehicles: arr };
}

// default export = array form (so tests keep working)
export default toFleetArray;
