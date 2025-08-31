// components/mapbox/layers/etaLayer.js
export function createEtaController(map, { id='route-etas', sourceId='route-etas-src' } = {}) {
  const SID = sourceId, LID = id;
  const project = ([lon,lat]) => {
    const R = 6378137, rad = Math.PI/180;
    return [R*lon*rad, R*Math.log(Math.tan(Math.PI/4 + (lat*rad)/2))];
  };
  const dist = (a,b) => {
    const [x1,y1] = project(a), [x2,y2] = project(b); return Math.hypot(x2-x1, y2-y1);
  };
  const fmt = (s) => {
    const sec = Math.round(s), m = Math.floor(sec/60), ss=sec%60, h=Math.floor(m/60);
    return h>0 ? `T+${h}:${String(m%60).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
               : `T+${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`;
  };
  const build = (coords, speedKmh, everyMeters) => {
    const speed = speedKmh*1000/3600; // m/s
    const features = [];
    let accD=0, accT=0;
    for (let i=1;i<coords.length;i++){
      const d = dist(coords[i-1], coords[i]); const t = d/speed;
      const prev = accD; accD+=d; accT+=t;
      if (Math.floor(prev/everyMeters) !== Math.floor(accD/everyMeters)) {
        features.push({ type:'Feature', geometry:{type:'Point', coordinates: coords[i]}, properties:{ eta: fmt(accT) }});
      }
    }
    features.push({ type:'Feature', geometry:{type:'Point', coordinates: coords.at(-1)}, properties:{ eta: fmt(accT) }});
    return { type:'FeatureCollection', features };
  };

  const api = {
    update(coords, { speedKmh=40, everyMeters=600, textColor='#ffffff', halo='#000000', haloWidth=2 } = {}) {
      const fc = build(coords, speedKmh, everyMeters);
      if (!map.getSource(SID)) map.addSource(SID, { type:'geojson', data: fc });
      else map.getSource(SID).setData(fc);
      if (!map.getLayer(LID)) {
        map.addLayer({
          id: LID, type:'symbol', source: SID,
          layout: {
            'text-field':['get','eta'], 'text-size':12, 'text-offset':[0,-0.8],
            'text-anchor':'bottom', 'text-allow-overlap': true
          },
          paint: {
            'text-color': textColor,
            'text-halo-color': halo,
            'text-halo-width': haloWidth,
            'text-opacity': 1
          }
        });
      } else {
        // allow runtime style tweaks
        map.setPaintProperty(LID, 'text-color', textColor);
        map.setPaintProperty(LID, 'text-halo-color', halo);
        map.setPaintProperty(LID, 'text-halo-width', haloWidth);
      }
    },
    setOpacity(o=1) {
      if (map.getLayer(LID)) map.setPaintProperty(LID, 'text-opacity', o);
    },
    remove() {
      if (map.getLayer(LID)) map.removeLayer(LID);
      if (map.getSource(SID)) map.removeSource(SID);
    }
  };
  return api;
}
