import "leaflet/dist/leaflet.css";

import type { Feature, FeatureCollection } from "geojson";
import type { Layer } from "leaflet";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

const API = "http://localhost:8000";
const PROV_DEFECTO = "34"; // Palencia (provincia de muestra)

const BUCKETS: [number, string][] = [
  [100000, "#08306b"],
  [20000, "#2171b5"],
  [5000, "#4292c6"],
  [1000, "#6baed6"],
  [500, "#9ecae1"],
  [100, "#c6dbef"],
  [0, "#deebf7"],
];

function color(pob: number | null): string {
  if (pob == null) return "#eeeeee";
  for (const [umbral, c] of BUCKETS) if (pob >= umbral) return c;
  return "#deebf7";
}

export default function App() {
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [anio, setAnio] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/coropleta.geojson?prov=${PROV_DEFECTO}`)
      .then((r) => r.json())
      .then((d: FeatureCollection & { properties?: { anio?: number } }) => {
        setGeo(d);
        setAnio(d.properties?.anio ?? null);
      })
      .catch(() => setError("No se pudo cargar /coropleta.geojson (¿API y BD arriba?)"));
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "system-ui" }}>
      <header style={{ padding: "0.5rem 1rem", borderBottom: "1px solid #eee" }}>
        <strong>territorio-engine</strong> — población por municipio · provincia {PROV_DEFECTO}
        {anio && <span> · año {anio}</span>}
        {error && <span style={{ color: "#b91c1c", marginLeft: "1rem" }}>{error}</span>}
      </header>
      <MapContainer center={[42.0, -4.5]} zoom={9} style={{ flex: 1 }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap"
        />
        {geo && (
          <GeoJSON
            data={geo}
            style={(f?: Feature) => ({
              fillColor: color(f?.properties?.poblacion_total ?? null),
              weight: 0.5,
              color: "#555",
              fillOpacity: 0.75,
            })}
            onEachFeature={(f: Feature, layer: Layer) => {
              const p = f.properties ?? {};
              const pob = p.poblacion_total ?? "—";
              layer.bindTooltip(`${p.nombre}: ${pob} hab`, { sticky: true });
            }}
          />
        )}
        <Leyenda />
      </MapContainer>
    </div>
  );
}

function Leyenda() {
  const items = [...BUCKETS].reverse();
  return (
    <div
      style={{
        position: "absolute",
        bottom: 20,
        right: 20,
        zIndex: 1000,
        background: "white",
        padding: "8px 10px",
        borderRadius: 6,
        boxShadow: "0 1px 4px rgba(0,0,0,.3)",
        fontSize: 12,
      }}
    >
      <strong>Habitantes</strong>
      {items.map(([umbral, c]) => (
        <div key={umbral} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, background: c, display: "inline-block" }} />≥ {umbral}
        </div>
      ))}
    </div>
  );
}
