import "leaflet/dist/leaflet.css";

import type { FeatureCollection } from "geojson";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

const API = "http://localhost:8000";
const PROV_DEFECTO = "34"; // Palencia (provincia de muestra para el mapa base)

export default function App() {
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API}/municipios.geojson?prov=${PROV_DEFECTO}`)
      .then((r) => r.json())
      .then(setGeo)
      .catch(() => setError("No se pudo cargar /municipios.geojson (¿API y BD arriba?)"));
  }, []);

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "system-ui" }}>
      <header style={{ padding: "0.5rem 1rem", borderBottom: "1px solid #eee" }}>
        <strong>territorio-engine</strong> — mapa base · municipios de la provincia {PROV_DEFECTO}
        {error && <span style={{ color: "#b91c1c", marginLeft: "1rem" }}>{error}</span>}
      </header>
      <MapContainer center={[42.0, -4.5]} zoom={9} style={{ flex: 1 }}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap"
        />
        {geo && <GeoJSON data={geo} style={{ color: "#2563eb", weight: 1, fillOpacity: 0.1 }} />}
      </MapContainer>
    </div>
  );
}
