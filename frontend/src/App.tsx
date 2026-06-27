import "leaflet/dist/leaflet.css";

import type { Feature, FeatureCollection, GeoJsonProperties } from "geojson";
import type { Layer } from "leaflet";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

const API = "/api"; // proxy de Vite → contenedor api (ver vite.config.ts)
const PROV_DEFECTO = "34"; // Palencia (provincia de muestra)

type Modo = "poblacion" | "envejecimiento" | "futuro";

const ESCALAS: Record<Modo, { endpoint: string; etiqueta: string; titulo: string; campo: string; sufijo: string; buckets: [number, string][] }> = {
  poblacion: {
    endpoint: "coropleta.geojson", etiqueta: "Población", titulo: "Habitantes", campo: "poblacion_total", sufijo: " hab",
    buckets: [[100000, "#08306b"], [20000, "#2171b5"], [5000, "#4292c6"], [1000, "#6baed6"], [500, "#9ecae1"], [100, "#c6dbef"], [0, "#deebf7"]],
  },
  envejecimiento: {
    endpoint: "envejecimiento.geojson", etiqueta: "Envejecimiento", titulo: "Índice envejec.", campo: "indice", sufijo: "",
    buckets: [[400, "#800026"], [200, "#bd0026"], [120, "#e31a1c"], [80, "#fc4e2a"], [40, "#feb24c"], [0, "#ffffb2"]],
  },
  futuro: {
    endpoint: "futuro.geojson", etiqueta: "Futuro", titulo: "Cambio a 2035", campo: "cambio_pct", sufijo: "%",
    buckets: [[20, "#006837"], [5, "#1a9850"], [0, "#a6d96a"], [-10, "#fdae61"], [-20, "#f46d43"], [-100, "#a50026"]],
  },
};

function color(buckets: [number, string][], v: number | null): string {
  if (v == null) return "#eeeeee";
  for (const [umbral, c] of buckets) if (v >= umbral) return c;
  return buckets[buckets.length - 1][1];
}

function tooltip(modo: Modo, p: GeoJsonProperties): string {
  const props = p ?? {};
  if (modo === "futuro") {
    const c = props.cambio_pct;
    const signo = c != null && c > 0 ? "+" : "";
    return `${props.nombre}: ${props.trayectoria ?? "—"} (${c != null ? signo + c + "%" : "—"} → ${props.pob_proyectada ?? "—"} hab en ${props.anio_horizonte ?? ""})`;
  }
  const esc = ESCALAS[modo];
  return `${props.nombre}: ${props[esc.campo] ?? "—"}${esc.sufijo}`;
}

export default function App() {
  const [modo, setModo] = useState<Modo>("poblacion");
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [anio, setAnio] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const esc = ESCALAS[modo];

  useEffect(() => {
    setGeo(null);
    setError(null);
    fetch(`${API}/${esc.endpoint}?prov=${PROV_DEFECTO}`)
      .then((r) => r.json())
      .then((d: FeatureCollection & { properties?: { anio?: number } }) => {
        setGeo(d);
        setAnio(d.properties?.anio ?? null);
      })
      .catch(() => setError(`No se pudo cargar /${esc.endpoint} (¿API y BD arriba?)`));
  }, [modo, esc.endpoint]);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "system-ui" }}>
      <header style={{ padding: "0.5rem 1rem", borderBottom: "1px solid #eee", display: "flex", gap: "1rem", alignItems: "center" }}>
        <strong>territorio-engine</strong>
        <span>provincia {PROV_DEFECTO}{anio ? ` · ${anio}` : ""}</span>
        <span style={{ marginLeft: "auto" }}>
          {(Object.keys(ESCALAS) as Modo[]).map((m) => (
            <button
              key={m}
              onClick={() => setModo(m)}
              style={{
                marginLeft: 6, padding: "4px 10px", cursor: "pointer", border: "1px solid #ccc", borderRadius: 4,
                background: modo === m ? "#2563eb" : "white", color: modo === m ? "white" : "#333",
              }}
            >
              {ESCALAS[m].etiqueta}
            </button>
          ))}
        </span>
        {error && <span style={{ color: "#b91c1c" }}>{error}</span>}
      </header>
      <MapContainer center={[42.0, -4.5]} zoom={9} style={{ flex: 1 }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap" />
        {geo && (
          <GeoJSON
            key={modo}
            data={geo}
            style={(f?: Feature) => ({
              fillColor: color(esc.buckets, (f?.properties?.[esc.campo] as number | null) ?? null),
              weight: 0.5, color: "#555", fillOpacity: 0.75,
            })}
            onEachFeature={(f: Feature, layer: Layer) => layer.bindTooltip(tooltip(modo, f.properties), { sticky: true })}
          />
        )}
        <Leyenda titulo={esc.titulo} buckets={esc.buckets} />
      </MapContainer>
    </div>
  );
}

function Leyenda({ titulo, buckets }: { titulo: string; buckets: [number, string][] }) {
  const items = [...buckets].reverse();
  return (
    <div style={{ position: "absolute", bottom: 20, right: 20, zIndex: 1000, background: "white", padding: "8px 10px", borderRadius: 6, boxShadow: "0 1px 4px rgba(0,0,0,.3)", fontSize: 12 }}>
      <strong>{titulo}</strong>
      {items.map(([umbral, c]) => (
        <div key={umbral} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, background: c, display: "inline-block" }} />≥ {umbral}
        </div>
      ))}
    </div>
  );
}
