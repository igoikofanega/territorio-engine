import "leaflet/dist/leaflet.css";

import type { Feature, FeatureCollection, GeoJsonProperties } from "geojson";
import L, { type Layer } from "leaflet";
import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";

const API = "/api"; // proxy de Vite → contenedor api (ver vite.config.ts)

type Modo = "indice" | "poblacion" | "renta" | "alquiler" | "paro" | "servicios" | "clima" | "envejecimiento" | "arquetipos" | "prediccion" | "futuro" | "futuro_cohorte";
type Prov = { cod: string; nombre: string; piramide: boolean };

type Sugerencia = { cod: string; nombre: string; provincia: string; cod_provincia: string };
type SerieRow = { anio: number; poblacion: number | null; paro: number | null; renta: number | null; alquiler: number | null; temp: number | null; precip: number | null };
type FichaData = {
  cod: string;
  nombre: string;
  provincia: { cod: string; nombre: string };
  superficie_km2: number | null;
  wiki: { descripcion: string | null; gentilicio: string | null; altitud: number | null; web: string | null; imagen: string | null; escudo: string | null; wiki_titulo: string | null } | null;
  serie: SerieRow[];
  indice: { anio: number; score: number | null; componentes: { renta: number | null; paro: number | null; alquiler: number | null; envejecimiento: number | null; servicios: number | null } } | null;
  prediccion: { anio_base: number; anio_horizonte: number; pob_base: number; pob_proyectada: number; cambio_pct: number; cambio_inf: number | null; cambio_sup: number | null; drivers: string | null } | null;
  arquetipo: { cluster: number; etiqueta: string } | null;
  servicios: { salud: number | null; educacion: number | null; comercio: number | null; total: number | null } | null;
  similares: { cod: string; nombre: string; provincia: string }[];
};

const FUT_BUCKETS: [number, string][] = [[20, "#006837"], [5, "#1a9850"], [0, "#a6d96a"], [-10, "#fdae61"], [-20, "#f46d43"], [-100, "#a50026"]];
// paleta cualitativa para arquetipos (clusters)
const PALETA_CAT = ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3"];

const ESCALAS: Record<
  Modo,
  { endpoint: string; etiqueta: string; titulo: string; campo: string; sufijo: string; anios?: string; categorico?: boolean; buckets: [number, string][] }
> = {
  arquetipos: {
    endpoint: "arquetipos.geojson", etiqueta: "Arquetipos", titulo: "Arquetipos", campo: "cluster", sufijo: "", categorico: true, buckets: [],
  },
  indice: {
    endpoint: "indice.geojson", etiqueta: "¿Dónde vivir?", titulo: "Índice 0-100", campo: "score", sufijo: "/100",
    buckets: [[70, "#006837"], [55, "#31a354"], [45, "#78c679"], [30, "#c2e699"], [0, "#ffffcc"]],
  },
  poblacion: {
    endpoint: "coropleta.geojson", etiqueta: "Población", titulo: "Habitantes", campo: "poblacion_total", sufijo: " hab", anios: "poblacion/anios",
    buckets: [[100000, "#08306b"], [20000, "#2171b5"], [5000, "#4292c6"], [1000, "#6baed6"], [500, "#9ecae1"], [100, "#c6dbef"], [0, "#deebf7"]],
  },
  renta: {
    endpoint: "renta.geojson", etiqueta: "Renta", titulo: "Renta €/persona", campo: "renta", sufijo: " €", anios: "renta/anios",
    buckets: [[20000, "#00441b"], [15000, "#238b45"], [12000, "#66c2a4"], [9000, "#b2e2e2"], [0, "#edf8fb"]],
  },
  alquiler: {
    endpoint: "alquiler.geojson", etiqueta: "Alquiler", titulo: "Alquiler €/m²", campo: "alquiler", sufijo: " €/m²", anios: "alquiler/anios",
    buckets: [[12, "#4a1486"], [9, "#6a51a3"], [7, "#9e9ac8"], [5, "#cbc9e2"], [0, "#f2f0f7"]],
  },
  paro: {
    endpoint: "paro.geojson", etiqueta: "Paro", titulo: "Paro ‰ hab", campo: "paro_1000", sufijo: "‰", anios: "paro/anios",
    buckets: [[150, "#67000d"], [100, "#cb181d"], [60, "#fb6a4a"], [30, "#fcae91"], [0, "#fee5d9"]],
  },
  servicios: {
    endpoint: "servicios.geojson", etiqueta: "Servicios", titulo: "Servicios ‰ hab (OSM)", campo: "serv_1000", sufijo: "‰",
    buckets: [[8, "#084594"], [4, "#2171b5"], [2, "#6baed6"], [1, "#c6dbef"], [0, "#f7fbff"]],
  },
  clima: {
    endpoint: "clima.geojson", etiqueta: "Clima", titulo: "Temp. media °C", campo: "temp", sufijo: " °C",
    buckets: [[18, "#d73027"], [15, "#fc8d59"], [12, "#fee090"], [9, "#91bfdb"], [0, "#4575b4"]],
  },
  envejecimiento: {
    endpoint: "envejecimiento.geojson", etiqueta: "Envejecimiento", titulo: "Índice envejec.", campo: "indice", sufijo: "", anios: "envejecimiento/anios",
    buckets: [[400, "#800026"], [200, "#bd0026"], [120, "#e31a1c"], [80, "#fc4e2a"], [40, "#feb24c"], [0, "#ffffb2"]],
  },
  prediccion: {
    endpoint: "prediccion.geojson", etiqueta: "Predicción ML", titulo: "Cambio a 2028", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
  futuro: {
    endpoint: "futuro.geojson", etiqueta: "Futuro (tendencia)", titulo: "Cambio a 2035", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
  futuro_cohorte: {
    endpoint: "futuro-cohorte.geojson", etiqueta: "Futuro (cohorte)", titulo: "Cambio a 2037", campo: "cambio_pct", sufijo: "%",
    buckets: FUT_BUCKETS,
  },
};

const CLAVES_INDICE = ["renta", "paro", "alquiler", "envejecimiento", "servicios"] as const;
type ClaveIndice = (typeof CLAVES_INDICE)[number];
type Pesos = Record<ClaveIndice, number>;
const PESOS_DEFECTO: Pesos = { renta: 0.25, paro: 0.20, alquiler: 0.20, envejecimiento: 0.15, servicios: 0.20 };
const CAMPO_COMP: Record<ClaveIndice, string> = {
  renta: "c_renta", paro: "c_paro", alquiler: "c_alquiler", envejecimiento: "c_envejecimiento", servicios: "c_servicios",
};

function combinaCustom(p: GeoJsonProperties, w: Pesos): number | null {
  const props = p ?? {};
  let num = 0, den = 0;
  for (const k of CLAVES_INDICE) {
    const v = props[CAMPO_COMP[k]] as number | null | undefined;
    if (v == null) continue;
    num += w[k] * v;
    den += w[k];
  }
  return den > 0 ? Math.round((num / den) * 10) / 10 : null;
}

function color(buckets: [number, string][], v: number | null): string {
  if (v == null) return "#eeeeee";
  for (const [umbral, c] of buckets) if (v >= umbral) return c;
  return buckets[buckets.length - 1][1];
}

function tooltip(modo: Modo, p: GeoJsonProperties, pesos?: Pesos): string {
  const props = p ?? {};
  if (modo === "indice") {
    const f = (v: unknown) => (v == null ? "—" : Math.round(v as number));
    const score = pesos ? combinaCustom(p, pesos) : (props.score as number | null);
    return `${props.nombre}: ${score ?? "—"}/100 · renta ${f(props.c_renta)} · empleo ${f(props.c_paro)} · asequibilidad ${f(props.c_alquiler)} · vitalidad ${f(props.c_envejecimiento)} · servicios ${f(props.c_servicios)}`;
  }
  if (modo === "servicios") {
    return `${props.nombre}: ${props.serv_1000 ?? "—"}‰ hab · 🏥 ${props.n_salud ?? 0} · 🎓 ${props.n_educacion ?? 0} · 🛒 ${props.n_comercio ?? 0}`;
  }
  if (modo === "clima") {
    return `${props.nombre}: ${props.temp ?? "—"} °C · ${props.precip ?? "—"} mm/año`;
  }
  if (modo === "arquetipos") {
    return `${props.nombre}: arquetipo ${props.cluster ?? "—"} · ${props.etiqueta ?? ""}`;
  }
  if (modo === "prediccion") {
    const c = props.cambio_pct;
    const signo = c != null && c > 0 ? "+" : "";
    const banda = props.cambio_inf != null ? ` [${props.cambio_inf}..${props.cambio_sup}]` : "";
    return `${props.nombre}: ${c != null ? signo + c + "%" : "—"}${banda} → ${props.pob_proyectada ?? "—"} hab (${props.anio_horizonte ?? ""}) · ${props.drivers ?? ""}`;
  }
  if (modo.startsWith("futuro")) {
    const c = props.cambio_pct;
    const signo = c != null && c > 0 ? "+" : "";
    return `${props.nombre}: ${props.trayectoria ?? "—"} (${c != null ? signo + c + "%" : "—"} → ${props.pob_proyectada ?? "—"} hab en ${props.anio_horizonte ?? ""})`;
  }
  const esc = ESCALAS[modo];
  return `${props.nombre}: ${props[esc.campo] ?? "—"}${esc.sufijo}`;
}

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
  const [prov, setProv] = useState("34");
  const [modo, setModo] = useState<Modo>("poblacion");
  const [anios, setAnios] = useState<number[]>([]);
  const [anioSel, setAnioSel] = useState<number | null>(null);
  const [geo, setGeo] = useState<FeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [codSel, setCodSel] = useState<string | null>(null);
  const [ficha, setFicha] = useState<FichaData | null>(null);
  const [pesos, setPesos] = useState<Pesos>(PESOS_DEFECTO);
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
    const q = esc.anios ? `?prov=${prov}&anio=${anioSel}` : `?prov=${prov}`;
    fetch(`${API}/${esc.endpoint}${q}`)
      .then((r) => r.json())
      .then(setGeo)
      .catch(() => setError(`No se pudo cargar /${esc.endpoint}`));
  }, [prov, modo, anioSel, esc.endpoint, esc.anios]);

  const sel = { padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc" };

  const categorias =
    esc.categorico && geo
      ? [...new Map(
          geo.features
            .filter((f) => f.properties?.cluster != null)
            .map((f) => [f.properties!.cluster as number, String(f.properties!.etiqueta)]),
        ).entries()]
          .sort((a, b) => a[0] - b[0])
          .map(([c, label]) => ({ color: PALETA_CAT[c % PALETA_CAT.length], label }))
      : null;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", fontFamily: "system-ui" }}>
      <header style={{ padding: "0.5rem 1rem", borderBottom: "1px solid #eee", display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
        <strong>territorio-engine</strong>
        <Buscador onSelect={(cod) => setCodSel(cod)} />
        <select value={prov} onChange={(e) => setProv(e.target.value)} style={sel}>
          {provincias.map((p) => (
            <option key={p.cod} value={p.cod}>{p.nombre}{!p.piramide ? " (sin pirámide)" : ""}</option>
          ))}
        </select>
        {esc.anios && (
          <select value={anioSel ?? ""} onChange={(e) => setAnioSel(Number(e.target.value))} style={sel}>
            {anios.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        )}
        <span style={{ marginLeft: "auto" }}>
          {(Object.keys(ESCALAS) as Modo[]).map((m) => (
            <button key={m} onClick={() => setModo(m)} style={{ marginLeft: 6, padding: "4px 10px", cursor: "pointer", border: "1px solid #ccc", borderRadius: 4, background: modo === m ? "#2563eb" : "white", color: modo === m ? "white" : "#333" }}>
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
            key={`${prov}-${modo}-${anioSel}-${modo === "indice" ? CLAVES_INDICE.map((k) => pesos[k].toFixed(2)).join(",") : ""}`}
            data={geo}
            style={(f?: Feature) => {
              let fillColor = "#eeeeee";
              if (esc.categorico) {
                const c = f?.properties?.cluster as number | null;
                fillColor = c != null ? PALETA_CAT[c % PALETA_CAT.length] : "#eeeeee";
              } else if (modo === "indice") {
                fillColor = color(esc.buckets, combinaCustom(f?.properties ?? null, pesos));
              } else {
                fillColor = color(esc.buckets, (f?.properties?.[esc.campo] as number | null) ?? null);
              }
              return { fillColor, weight: 0.5, color: "#555", fillOpacity: 0.75 };
            }}
            onEachFeature={(f: Feature, layer: Layer) => {
              layer.bindTooltip(tooltip(modo, f.properties, modo === "indice" ? pesos : undefined), { sticky: true });
              layer.on("click", () => {
                const cod = (f.properties as GeoJsonProperties)?.cod_municipio as string | undefined;
                if (cod) setCodSel(cod);
              });
            }}
          />
        )}
        <FitBounds geo={geo} />
        <Leyenda titulo={esc.titulo} buckets={esc.buckets} categorias={categorias} />
        {modo === "indice" && <PanelPesos pesos={pesos} onChange={setPesos} />}
      </MapContainer>
      {codSel && (
        <Ficha
          ficha={ficha}
          onClose={() => setCodSel(null)}
          onSelect={(c) => setCodSel(c)}
        />
      )}
    </div>
  );
}

function PanelPesos({ pesos, onChange }: { pesos: Pesos; onChange: (p: Pesos) => void }) {
  const [abierto, setAbierto] = useState(false);
  const suma = CLAVES_INDICE.reduce((s, k) => s + pesos[k], 0);
  const norm: Pesos = { ...pesos };
  if (suma > 0) for (const k of CLAVES_INDICE) norm[k] = pesos[k] / suma;
  const dirty = CLAVES_INDICE.some((k) => Math.abs(pesos[k] - PESOS_DEFECTO[k]) > 0.001);
  return (
    <div style={{ position: "absolute", top: 16, left: 60, zIndex: 1000, background: "white", padding: "8px 12px", borderRadius: 6, boxShadow: "0 1px 4px rgba(0,0,0,.3)", fontSize: 12, minWidth: 240 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => setAbierto((v) => !v)}>
        <strong>Pesos</strong>
        <span style={{ color: "#666" }}>{abierto ? "▾" : "▸"}</span>
        {dirty && <span style={{ marginLeft: "auto", color: "#2563eb", fontSize: 10 }}>ajustado</span>}
      </div>
      {abierto && (
        <div style={{ marginTop: 6 }}>
          {CLAVES_INDICE.map((k) => (
            <label key={k} style={{ display: "flex", alignItems: "center", gap: 6, margin: "3px 0" }}>
              <span style={{ width: 90, color: "#555", textTransform: "capitalize" }}>{k}</span>
              <input
                type="range" min={0} max={1} step={0.05}
                value={pesos[k]}
                onChange={(e) => onChange({ ...pesos, [k]: Number(e.target.value) })}
                style={{ flex: 1 }}
              />
              <span style={{ width: 32, textAlign: "right", color: "#333" }}>{Math.round(norm[k] * 100)}%</span>
            </label>
          ))}
          <button
            onClick={() => onChange(PESOS_DEFECTO)}
            style={{ marginTop: 4, border: 0, background: "#f3f4f6", padding: "3px 8px", borderRadius: 4, cursor: "pointer", fontSize: 11 }}
          >
            restablecer
          </button>
        </div>
      )}
    </div>
  );
}

function Buscador({ onSelect }: { onSelect: (cod: string) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Sugerencia[]>([]);
  const [abierto, setAbierto] = useState(false);
  const [cursor, setCursor] = useState(0);

  useEffect(() => {
    if (q.trim().length < 2) { setItems([]); return; }
    const id = setTimeout(() => {
      fetch(`${API}/buscar?q=${encodeURIComponent(q.trim())}`)
        .then((r) => r.json())
        .then((d: Sugerencia[]) => { setItems(d); setCursor(0); })
        .catch(() => setItems([]));
    }, 150);
    return () => clearTimeout(id);
  }, [q]);

  const pick = (s: Sugerencia) => {
    onSelect(s.cod);
    setQ(""); setItems([]); setAbierto(false);
  };

  return (
    <div style={{ position: "relative", width: 240 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); setAbierto(true); }}
        onFocus={() => setAbierto(true)}
        onBlur={() => setTimeout(() => setAbierto(false), 150)}
        onKeyDown={(e) => {
          if (!items.length) return;
          if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => (c + 1) % items.length); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => (c - 1 + items.length) % items.length); }
          else if (e.key === "Enter") { e.preventDefault(); pick(items[cursor]); }
          else if (e.key === "Escape") { setAbierto(false); }
        }}
        placeholder="Buscar municipio…"
        style={{ padding: "4px 8px", borderRadius: 4, border: "1px solid #ccc", width: "100%", boxSizing: "border-box" }}
      />
      {abierto && items.length > 0 && (
        <ul style={{ position: "absolute", top: "100%", left: 0, right: 0, margin: 0, padding: 0, listStyle: "none", background: "white", border: "1px solid #ccc", borderRadius: 4, maxHeight: 260, overflowY: "auto", zIndex: 1200, boxShadow: "0 2px 8px rgba(0,0,0,.15)" }}>
          {items.map((s, i) => (
            <li
              key={s.cod}
              onMouseDown={() => pick(s)}
              onMouseEnter={() => setCursor(i)}
              style={{ padding: "4px 8px", cursor: "pointer", background: i === cursor ? "#eff6ff" : "white", fontSize: 12 }}
            >
              <strong>{s.nombre}</strong>
              <span style={{ color: "#666" }}> · {s.provincia}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Sparkline({ serie }: { serie: SerieRow[] }) {
  const pts = serie.filter((r) => r.poblacion != null);
  if (pts.length < 2) return null;
  const w = 240, h = 48, pad = 4;
  const xs = pts.map((r) => r.anio);
  const ys = pts.map((r) => r.poblacion as number);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = (x: number) => pad + ((x - xmin) / (xmax - xmin || 1)) * (w - 2 * pad);
  const sy = (y: number) => h - pad - ((y - ymin) / (ymax - ymin || 1)) * (h - 2 * pad);
  const d = pts.map((r, i) => `${i === 0 ? "M" : "L"}${sx(r.anio)},${sy(r.poblacion as number)}`).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <path d={d} fill="none" stroke="#2563eb" strokeWidth={1.5} />
      <text x={pad} y={h - 1} fontSize={9} fill="#666">{xmin}</text>
      <text x={w - pad} y={h - 1} fontSize={9} fill="#666" textAnchor="end">{xmax}</text>
      <text x={pad} y={10} fontSize={9} fill="#666">{ymax.toLocaleString("es")}</text>
    </svg>
  );
}

function Componente({ nombre, valor }: { nombre: string; valor: number | null }) {
  const v = valor == null ? 0 : Math.round(valor);
  const bg = valor == null ? "#eee" : "#dbeafe";
  const fg = valor == null ? "#999" : "#1d4ed8";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
      <span style={{ width: 90, color: "#555" }}>{nombre}</span>
      <span style={{ flex: 1, background: bg, height: 8, borderRadius: 4, overflow: "hidden" }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: fg }} />
      </span>
      <span style={{ width: 30, textAlign: "right", color: "#333" }}>{valor == null ? "—" : v}</span>
    </div>
  );
}

function Ficha({ ficha, onClose, onSelect }: { ficha: FichaData | null; onClose: () => void; onSelect: (cod: string) => void }) {
  const panel: CSSProperties = {
    position: "absolute", top: 60, right: 12, bottom: 12, width: 340, zIndex: 1100,
    background: "white", boxShadow: "0 2px 12px rgba(0,0,0,.25)", borderRadius: 8,
    padding: 14, overflowY: "auto", fontFamily: "system-ui", fontSize: 13, color: "#333",
  };
  if (!ficha) {
    return (
      <div style={panel}>
        <button onClick={onClose} style={{ float: "right", border: 0, background: "transparent", cursor: "pointer", fontSize: 18 }}>×</button>
        <p>Cargando…</p>
      </div>
    );
  }
  const pred = ficha.prediccion;
  const idx = ficha.indice;
  return (
    <div style={panel}>
      <button onClick={onClose} style={{ float: "right", border: 0, background: "transparent", cursor: "pointer", fontSize: 18, lineHeight: 1 }}>×</button>
      <h2 style={{ margin: "0 0 2px 0", fontSize: 18 }}>{ficha.nombre}</h2>
      <div style={{ color: "#666", fontSize: 12, marginBottom: 8 }}>
        {ficha.provincia.nombre}
        {ficha.wiki?.gentilicio ? ` · ${ficha.wiki.gentilicio}` : ""}
        {ficha.superficie_km2 ? ` · ${ficha.superficie_km2.toFixed(1)} km²` : ""}
        {ficha.wiki?.altitud ? ` · ${Math.round(ficha.wiki.altitud)} m` : ""}
      </div>
      {ficha.wiki?.imagen && (
        <img src={ficha.wiki.imagen} alt="" style={{ width: "100%", borderRadius: 4, marginBottom: 8, maxHeight: 140, objectFit: "cover" }} />
      )}
      {ficha.wiki?.descripcion && (
        <p style={{ margin: "0 0 10px 0", lineHeight: 1.35 }}>{ficha.wiki.descripcion}</p>
      )}

      <Sparkline serie={ficha.serie} />

      {idx && (
        <>
          <h3 style={{ margin: "12px 0 4px 0", fontSize: 13 }}>¿Dónde vivir? <span style={{ color: "#2563eb" }}>{idx.score ?? "—"}/100</span></h3>
          <Componente nombre="renta" valor={idx.componentes.renta} />
          <Componente nombre="empleo" valor={idx.componentes.paro} />
          <Componente nombre="asequibilidad" valor={idx.componentes.alquiler} />
          <Componente nombre="vitalidad" valor={idx.componentes.envejecimiento} />
          <Componente nombre="servicios" valor={idx.componentes.servicios} />
        </>
      )}

      {pred && (
        <>
          <h3 style={{ margin: "12px 0 4px 0", fontSize: 13 }}>Predicción a {pred.anio_horizonte}</h3>
          <div>
            <strong style={{ color: pred.cambio_pct >= 0 ? "#166534" : "#991b1b" }}>
              {pred.cambio_pct >= 0 ? "+" : ""}{pred.cambio_pct}%
            </strong>
            {pred.cambio_inf != null && (
              <span style={{ color: "#666" }}> [{pred.cambio_inf}%..{pred.cambio_sup}%]</span>
            )}
            <span style={{ color: "#666" }}> → {pred.pob_proyectada.toLocaleString("es")} hab</span>
          </div>
          {pred.drivers && <div style={{ color: "#666", fontSize: 11, marginTop: 2 }}>{pred.drivers}</div>}
        </>
      )}

      {ficha.arquetipo && (
        <div style={{ marginTop: 10 }}>
          <span style={{ background: "#f3f4f6", padding: "3px 8px", borderRadius: 10, fontSize: 11 }}>
            Arquetipo #{ficha.arquetipo.cluster}: {ficha.arquetipo.etiqueta}
          </span>
        </div>
      )}

      {ficha.servicios && (
        <>
          <h3 style={{ margin: "12px 0 4px 0", fontSize: 13 }}>Servicios (OSM)</h3>
          <div style={{ color: "#555" }}>
            🏥 {ficha.servicios.salud ?? 0} · 🎓 {ficha.servicios.educacion ?? 0} · 🛒 {ficha.servicios.comercio ?? 0}
            <span style={{ color: "#999" }}> (total {ficha.servicios.total ?? 0})</span>
          </div>
        </>
      )}

      {ficha.similares.length > 0 && (
        <>
          <h3 style={{ margin: "12px 0 4px 0", fontSize: 13 }}>Pueblos como {ficha.nombre}</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {ficha.similares.map((s) => (
              <button
                key={s.cod}
                onClick={() => onSelect(s.cod)}
                title={s.provincia}
                style={{ background: "#eef2ff", color: "#3730a3", border: 0, borderRadius: 10, padding: "3px 8px", fontSize: 11, cursor: "pointer" }}
              >
                {s.nombre}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Leyenda({ titulo, buckets, categorias }: { titulo: string; buckets: [number, string][]; categorias?: { color: string; label: string }[] | null }) {
  const items = categorias ?? [...buckets].reverse().map(([u, c]) => ({ color: c, label: `≥ ${u}` }));
  return (
    <div style={{ position: "absolute", bottom: 20, right: 20, zIndex: 1000, background: "white", padding: "8px 10px", borderRadius: 6, boxShadow: "0 1px 4px rgba(0,0,0,.3)", fontSize: 12, maxWidth: 220 }}>
      <strong>{titulo}</strong>
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 14, height: 14, background: it.color, display: "inline-block", flexShrink: 0 }} />
          {it.label}
        </div>
      ))}
    </div>
  );
}
