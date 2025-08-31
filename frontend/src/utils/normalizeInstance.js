// Guarantees map-safe coordinates while preserving planar x/y.
export function normalizeInstanceResponse(loadResp) {
    const data = loadResp?.data ?? loadResp ?? {};
    const waypoints = (data.waypoints || []).map((w, i) => {
        // Prefer provided display coords; else fall back to lon/lat; else derive from x/y (if you already created them)
        const displayLon = Number(
            w.display_lon ?? w.lon ?? (Number.isFinite(w.y) ? w.y : undefined)
        );
        const displayLat = Number(
            w.display_lat ?? w.lat ?? (Number.isFinite(w.x) ? w.x : undefined)
        );

        return {
            ...w,
            // keep planar if present (many backends use lat=x, lon=y for EUC_2D)
            x: Number.isFinite(w.x) ? Number(w.x) : (Number.isFinite(w.lat) ? Number(w.lat) : undefined),
            y: Number.isFinite(w.y) ? Number(w.y) : (Number.isFinite(w.lon) ? Number(w.lon) : undefined),

            // map-friendly
            coordinates: [
                Number.isFinite(displayLon) ? displayLon : 0,
                Number.isFinite(displayLat) ? displayLat : 0
            ],
        };
    });

    return { ...data, waypoints };
}
