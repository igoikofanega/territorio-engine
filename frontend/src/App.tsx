import "leaflet/dist/leaflet.css";

import type { Feature, FeatureCollection, GeoJsonProperties } from "geojson";
import L, { type Layer, type PathOptions } from "leaflet";
import { PanelLeftOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, ScaleControl, TileLayer, useMap, ZoomControl } from "react-leaflet";

import Ficha from "./components/Ficha";
import Leyenda from "./components/Leyenda";
import Comparar from "./components/Comparar";
import Dashboard from "./components/Dashboard";
import Recomendador from "./components/Recomendador";
import Sidebar from "./components/Sidebar";
import { color, combinaCustom, ESCALAS, INFLEXION_COLORES, INFLEXION_LEYENDA, LISA_COLORES, LISA_LEYENDA, PALETA_CAT, PESOS_DEFECTO, tooltip } from "./escalas";
import { CLAVES_INDICE, type FichaData, type Modo, type Pesos, type Prov } from "./types";

const API = "/api"; // proxy de Vite → contenedor api (ver vite.config.ts)

function FitBounds({ geo }: { geo: FeatureCollection | null }) {
  const map = useMap();
  useEffect(() => {
    if (geo && geo.features.length) {
      const b = L.geoJSON(geo).getBounds();
      if (b.isValid()) map.fitBounds(b, { padding: [20, 20] });
    }
  }, [geo, map]);
  return null;
}

export default function App() {
  const [provincias, setProvincias] = useState<Prov[]>([]);
  const [prov, setProv] = useState("31"); // Navarra por defecto
  const [modo, setModo] = useState<Modo>("poblacion");
  const [anios, setAnios] = useState<number[]>([]);
  const [anioSel, setAnioSel] = useState<number | null>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codSel, setCodSel] = useState<string | null>(null);
  const [ficha, setFicha] = useState<FichaData | null>(null);
  const [pesos, setPesos] = useState<Pesos>(PESOS_DEFECTO);
  const [sidebarAbierta, setSidebarAbierta] = useState(true);
  const [recomendadorAbierto, setRecomendadorAbierto] = useState(false);
  const [compararAbierto, setCompararAbierto] = useState(false);
  const [vista, setVista] = useState<"mapa" | "resumen">("mapa");
  const esc = ESCALAS[modo];

  useEffect(() => {
    if (!codSel) { setFicha(null); return; }
    fetch(`${API}/municipio/${codSel}`).then((r) => r.json()).then((d: FichaData) => {
      setFicha(d);
      // si el municipio está en otra provincia, cambiamos el mapa para que se vea
      if (d?.provincia?.cod && d.provincia.cod !== prov) setProv(d.provincia.cod);
    }).catch(() => setFicha(null));
  }, [codSel]);

  useEffect(() => {
    fetch(`${API}/provincias`).then((r) => r.json()).then(setProvincias).catch(() => {});
  }, []);

  // Años disponibles según el modo
  useEffect(() => {
    if (!esc.anios) {
      setAnios([]);
      setAnioSel(null);
      return;
    }
    fetch(`${API}/${esc.anios}`).then((r) => r.json()).then((ys: number[]) => {
      setAnios(ys);
      setAnioSel(ys[0] ?? null);
    }).catch(() => {});
  }, [modo, esc.anios]);

  // Datos del mapa
  useEffect(() => {
    if (esc.anios && anioSel == null) return; // esperando a tener año
    setError(null);
    const sep = esc.endpoint.includes("?") ? "&" : "?";
    const q = esc.anios ? `${sep}prov=${prov}&anio=${anioSel}` : `${sep}prov=${prov}`;
    fetch(`${API}/${esc.endpoint}${q}`)
      .then((r) => r.json())
      .then(setGeo)
      .catch(() => setError(`No se pudo cargar /${esc.endpoint}`));
  }, [prov, modo, anioSel, esc.endpoint, esc.anios]);

  const categorias = modo.startsWith("lisa_")
    ? LISA_LEYENDA
    : modo === "inflexion"
    ? INFLEXION_LEYENDA
    : esc.categorico && geo
      ? [...new Map(
          geo.features
            .filter((f) => f.properties?.cluster != null)
            .map((f) => [f.properties!.cluster as number, String(f.properties!.etiqueta)]),
        ).entries()]
          .sort((a, b) => a[0] - b[0])
          .map(([c, label]) => ({ color: PALETA_CAT[c % PALETA_CAT.length], label }))
      : null;

  const pesosDirty = CLAVES_INDICE.some((k) => Math.abs(pesos[k] - PESOS_DEFECTO[k]) > 0.001);

  const estiloBase = (f?: Feature): PathOptions => {
    let fillColor = "#e2e8f0";
    if (modo.startsWith("lisa_")) {
      fillColor = LISA_COLORES[(f?.properties?.categoria as string) ?? ""] ?? "#e2e8f0";
    } else if (modo === "inflexion") {
      fillColor = INFLEXION_COLORES[(f?.properties?.tipo as string) ?? ""] ?? "#e8e8e8";
    } else if (esc.categorico) {
      const c = f?.properties?.cluster as number | null;
      fillColor = c != null ? PALETA_CAT[c % PALETA_CAT.length] : "#e2e8f0";
    } else if (modo === "indice") {
      fillColor = color(esc.buckets, combinaCustom(f?.properties ?? null, pesos));
    } else {
      fillColor = color(esc.buckets, (f?.properties?.[esc.campo] as number | null) ?? null);
    }
    const seleccionado = codSel != null && f?.properties?.cod_municipio === codSel;
    return seleccionado
      ? { fillColor, weight: 2.5, color: "#2563eb", fillOpacity: 0.9 }
      : { fillColor, weight: 0.6, color: "#ffffff", fillOpacity: 0.85 };
  };

  return (
    <div style={{ height: "100vh", display: "flex" }}>
      {sidebarAbierta && (
        <Sidebar
          provincias={provincias}
          prov={prov}
          onProv={setProv}
          modo={modo}
          onModo={setModo}
          anios={anios}
          anioSel={anioSel}
          onAnio={setAnioSel}
          pesos={pesos}
          onPesos={setPesos}
          onSelectMunicipio={setCodSel}
          onColapsar={() => setSidebarAbierta(false)}
          onRecomendador={() => setRecomendadorAbierto((v) => !v)}
          onComparar={() => setCompararAbierto(true)}
          vista={vista}
          onVista={setVista}
          nMunicipios={geo?.features.length ?? null}
          error={error}
        />
      )}
      <div style={{ flex: 1, position: "relative" }}>
        {!sidebarAbierta && (
          <button
            className="panel btn-ghost"
            onClick={() => setSidebarAbierta(true)}
            title="Mostrar panel"
            style={{ position: "absolute", top: 12, left: 12, zIndex: 1000, width: 32, height: 32, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text)" }}
          >
            <PanelLeftOpen size={16} strokeWidth={1.75} />
          </button>
        )}
        {vista === "resumen" ? (
          <Dashboard
            prov={prov}
            ambitoNombre={provincias.find((p) => p.cod === prov)?.nombre ?? "España"}
            onSelect={(c) => { setVista("mapa"); setCodSel(c); }}
          />
        ) : (
        <MapContainer center={[42.0, -4.5]} zoom={9} style={{ height: "100%" }} zoomControl={false}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          {geo && (
            <GeoJSON
              key={`${prov}-${modo}-${anioSel}-${codSel ?? ""}-${modo === "indice" ? CLAVES_INDICE.map((k) => pesos[k].toFixed(2)).join(",") : ""}`}
              data={geo}
              style={estiloBase}
              onEachFeature={(f: Feature, layer: Layer) => {
                layer.bindTooltip(tooltip(modo, f.properties, modo === "indice" ? pesos : undefined), { sticky: true });
                layer.on("click", () => {
                  const cod = (f.properties as GeoJsonProperties)?.cod_municipio as string | undefined;
                  if (cod) setCodSel(cod);
                });
                layer.on("mouseover", () => {
                  (layer as L.Path).setStyle({ weight: 2, color: "#334155" });
                  (layer as L.Path).bringToFront();
                });
                layer.on("mouseout", () => {
                  (layer as L.Path).setStyle(estiloBase(f));
                });
              }}
            />
          )}
          <ZoomControl position="bottomleft" />
          <ScaleControl position="bottomleft" imperial={false} />
          <FitBounds geo={geo} />
          <Leyenda
            titulo={esc.titulo}
            buckets={esc.buckets}
            categorias={categorias}
            nota={modo === "indice" && pesosDirty ? "pesos ajustados" : null}
          />
        </MapContainer>
        )}
        {recomendadorAbierto && (
          <Recomendador
            pesos={pesos}
            onSelect={(c) => setCodSel(c)}
            onClose={() => setRecomendadorAbierto(false)}
          />
        )}
        {compararAbierto && (
          <Comparar codA={codSel} codB={null} onClose={() => setCompararAbierto(false)} />
        )}
        {codSel && (
          <Ficha
            ficha={ficha}
            onClose={() => setCodSel(null)}
            onSelect={(c) => setCodSel(c)}
          />
        )}
      </div>
    </div>
  );
}
