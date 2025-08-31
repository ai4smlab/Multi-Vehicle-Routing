# Tutorials

## 1) First route (TSP, 3 points)

1. Open **http://localhost:3000/map/maplibre**.
2. Click three locations to add waypoints. In the Waypoint Sidebar, ensure point **0** is the depot.
3. Open **Solver Panel**:
   - Solver: `ortools`
   - Adapter: `haversine`
4. Click **Solve**.
5. Check **Result Summary**: distance/time; in the map the route appears.
6. Open **Route Tools Panel**:
   - **Show ETA** → ETA dots on segments
   - **Hide ETA** → hides
   - **Clear ETA** → clears ETA fields from the route

## 2) Solomon VRPTW (c101)

1. Sidebar → **Benchmark Selector**.
2. Dataset: `solomon` → search `c101` → **Load**.
3. It will:
   - Detect **planar** coords → force adapter **euclidean (local)**.
   - Create a default fleet (10 vehicles, cap=200).
   - Build a matrix with **seconds** durations.
4. Click **Solve loaded & compare**.
5. The summary shows total distance/time per vehicle and (if available) the **best-known** comparison.
6. If infeasible:
   - Confirm service times/time windows are in **seconds**.
   - Ensure vehicles have cap `[200]`.
   - Keep depot time window wide (0..1e9).

## 3) Real-World Dataset (OSM POIs)

**Place mode**
1. Open **Real-World Dataset (OSM POIs)** panel.
2. Place: `Paris, France` | Key: `amenity` | Value: `restaurant|cafe` | Limit: `300`.
3. **Search** → inspect feature count.
4. **Load to Map** to show points. Use saved dataset tools to toggle/hide.
5. **🧹 Clear ALL RWD layers** removes everything added by this panel.

**BBox mode**
1. Toggle **Draw BBox on map**, then drag to draw the rectangle.
2. Click **Use drawn bbox** → Key/Value as above → **Search**.
3. **Load to Map** or **Save to Saved datasets**.

## 4) Switching adapters

- **Planar datasets** (Solomon, EUC_2D, VRPLIB): use **euclidean (local)**.
- **Real world lon/lat**: try **osm_graph** first (no API keys), else **haversine** as a baseline.

**Distance Matrix (osm_graph)** example in code:

```js
const payload = {
  adapter: 'osm_graph',
  mode: 'driving',
  parameters: { metrics: ['distance','duration'], units: 'm' },
  coordinates: coordsLL.map(([lon,lat]) => ({lon,lat}))
}
```

## 5) Exporting / Reproducing

- **Export GeoJSON**: panels have “Download GeoJSON”.
- **Copy debug payload**: BenchmarkSelector logs a copy-pastable JSON block to console with:
  - dataset/name/vrpType
  - vehicles (normalized)
  - demands / service / windows
  - matrix stats (checksum, mins/max)
Use it in issues to reproduce exactly.

## 6) Known good flows

- **(ortools + euclidean + c101)** → feasible VRPTW, 10 vehicles, TW in seconds
- **(vroom + waypoints only)** → fallback to NN if pyvroom can’t accept indices/coords; now handled
- **(TSP + haversine)** → small examples under a second
