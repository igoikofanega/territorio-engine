import {
  ArrowDownRight,
  ArrowUpRight,
  Briefcase,
  GraduationCap,
  Home,
  ShoppingCart,
  Stethoscope,
  Users,
  UsersRound,
  Wallet,
  X,
} from "lucide-react";

import type { FichaData, SerieRow } from "../types";
import Sparkline from "./Sparkline";

/** Último valor no nulo de un campo de la serie + el anterior (para el delta). */
function ultimo(serie: SerieRow[], campo: keyof SerieRow): { anio: number; valor: number; prev: number | null } | null {
  const rows = serie.filter((r) => r[campo] != null);
  if (!rows.length) return null;
  const last = rows[rows.length - 1];
  const prev = rows.length > 1 ? rows[rows.length - 2] : null;
  return { anio: last.anio, valor: last[campo] as number, prev: prev ? (prev[campo] as number) : null };
}

function StatCard({
  icono: Icono,
  label,
  valor,
  unidad,
  anio,
  delta,
  deltaSemantico,
}: {
  icono: typeof Users;
  label: string;
  valor: string;
  unidad?: string;
  anio?: number;
  delta?: number | null;
  deltaSemantico?: boolean; // colorear verde/rojo (solo cuando subir es inequívocamente bueno)
}) {
  return (
    <div className="stat-card">
      <div className="stat-label">
        <Icono size={12} strokeWidth={1.75} />
        {label}
        {anio != null && <span style={{ marginLeft: "auto", fontWeight: 400 }}>{anio}</span>}
      </div>
      <div className="stat-valor">
        {valor}
        {unidad && <span className="stat-unidad">{unidad}</span>}
      </div>
      {delta != null && Number.isFinite(delta) && (
        <div className="stat-delta" style={deltaSemantico ? { color: delta >= 0 ? "#15803d" : "#b91c1c" } : undefined}>
          {delta >= 0 ? <ArrowUpRight size={11} strokeWidth={2} /> : <ArrowDownRight size={11} strokeWidth={2} />}
          {Math.abs(delta).toFixed(1)}% vs año anterior
        </div>
      )}
    </div>
  );
}

/** Anillo de progreso 0-100 para el score del índice. */
function Gauge({ valor }: { valor: number | null }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const frac = valor == null ? 0 : Math.max(0, Math.min(1, valor / 100));
  return (
    <svg width={68} height={68} viewBox="0 0 68 68" style={{ flexShrink: 0 }}>
      <circle cx={34} cy={34} r={r} fill="none" stroke="var(--border)" strokeWidth={6} />
      <circle
        cx={34} cy={34} r={r} fill="none"
        stroke="var(--accent)" strokeWidth={6} strokeLinecap="round"
        strokeDasharray={`${frac * c} ${c}`}
        transform="rotate(-90 34 34)"
      />
      <text x={34} y={33} textAnchor="middle" fontSize={17} fontWeight={700} fill="var(--text)">
        {valor ?? "—"}
      </text>
      <text x={34} y={46} textAnchor="middle" fontSize={8} fill="var(--text-2)">
        /100
      </text>
    </svg>
  );
}

function Componente({ nombre, valor }: { nombre: string; valor: number | null }) {
  const v = valor == null ? 0 : Math.round(valor);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, margin: "4px 0" }}>
      <span style={{ width: 86, color: "var(--text-2)" }}>{nombre}</span>
      <span style={{ flex: 1, background: valor == null ? "var(--border)" : "var(--accent-soft)", height: 6, borderRadius: 3, overflow: "hidden" }}>
        <span style={{ display: "block", width: `${v}%`, height: "100%", background: "var(--accent)", borderRadius: 3 }} />
      </span>
      <span style={{ width: 26, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{valor == null ? "—" : v}</span>
    </div>
  );
}

export default function Ficha({ ficha, onClose, onSelect }: { ficha: FichaData | null; onClose: () => void; onSelect: (cod: string) => void }) {
  if (!ficha) {
    return (
      <div className="ficha" style={{ padding: 16 }}>
        <button className="btn-ghost" onClick={onClose} style={{ float: "right" }}><X size={16} /></button>
        <p style={{ color: "var(--text-2)" }}>Cargando…</p>
      </div>
    );
  }
  const pred = ficha.prediccion;
  const idx = ficha.indice;
  const foto = ficha.wiki?.imagen;

  const pob = ultimo(ficha.serie, "poblacion");
  const renta = ultimo(ficha.serie, "renta");
  const alquiler = ultimo(ficha.serie, "alquiler");
  const paro = ultimo(ficha.serie, "paro");
  const extranjeros = ultimo(ficha.serie, "pct_extranjeros");
  // paro absoluto → ‰ sobre la población del mismo año (si la hay)
  const paroPct =
    paro && pob
      ? { ...paro, valor: (paro.valor / (ficha.serie.find((r) => r.anio === paro.anio)?.poblacion ?? pob.valor)) * 1000 }
      : null;
  const deltaPct = (d: { valor: number; prev: number | null } | null) =>
    d && d.prev != null && d.prev !== 0 ? ((d.valor - d.prev) / d.prev) * 100 : null;

  return (
    <div className="ficha">
      {/* cabecera: foto con gradiente o bloque de color plano */}
      <div
        style={{
          position: "relative",
          height: foto ? 150 : 84,
          background: foto ? `url(${foto}) center/cover` : "linear-gradient(135deg, #1e3a8a, #2563eb)",
        }}
      >
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(15,23,42,0) 30%, rgba(15,23,42,.75))" }} />
        <button
          className="btn-ghost"
          onClick={onClose}
          style={{ position: "absolute", top: 8, right: 8, color: "white", background: "rgba(15,23,42,.45)", width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 6 }}
        >
          <X size={15} strokeWidth={2} />
        </button>
        <div style={{ position: "absolute", left: 16, right: 16, bottom: 10, color: "white" }}>
          <div style={{ fontSize: 20, fontWeight: 700, letterSpacing: "-0.02em", textShadow: "0 1px 3px rgba(0,0,0,.5)" }}>{ficha.nombre}</div>
          <div style={{ fontSize: 11, opacity: 0.9 }}>
            {ficha.provincia.nombre}
            {ficha.wiki?.gentilicio ? ` · ${ficha.wiki.gentilicio}` : ""}
            {ficha.superficie_km2 ? ` · ${ficha.superficie_km2.toFixed(1)} km²` : ""}
            {ficha.wiki?.altitud ? ` · ${Math.round(ficha.wiki.altitud)} m` : ""}
          </div>
        </div>
      </div>

      <div style={{ padding: 16 }}>
        {ficha.wiki?.descripcion && (
          <p style={{ margin: "0 0 14px", lineHeight: 1.45, color: "var(--text)" }}>{ficha.wiki.descripcion}</p>
        )}

        {/* KPIs: etiqueta → valor → delta (indicadores más recientes) */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {pob && (
            <StatCard
              icono={Users} label="Población" anio={pob.anio}
              valor={pob.valor.toLocaleString("es")} unidad="hab"
              delta={deltaPct(pob)} deltaSemantico
            />
          )}
          {renta && (
            <StatCard
              icono={Wallet} label="Renta" anio={renta.anio}
              valor={Math.round(renta.valor).toLocaleString("es")} unidad="€/pers"
              delta={deltaPct(renta)}
            />
          )}
          {paroPct && (
            <StatCard
              icono={Briefcase} label="Paro" anio={paroPct.anio}
              valor={paroPct.valor.toFixed(0)} unidad="‰ hab"
            />
          )}
          {alquiler && (
            <StatCard
              icono={Home} label="Alquiler" anio={alquiler.anio}
              valor={alquiler.valor.toFixed(1)} unidad="€/m²"
              delta={deltaPct(alquiler)}
            />
          )}
          {extranjeros && (
            <StatCard
              icono={UsersRound} label="Extranjeros" anio={extranjeros.anio}
              valor={extranjeros.valor.toFixed(1)} unidad="%"
              delta={deltaPct(extranjeros)}
            />
          )}
        </div>

        <h3>Evolución de la población</h3>
        <Sparkline serie={ficha.serie} />

        {idx && (
          <>
            <h3>¿Dónde vivir?</h3>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <Gauge valor={idx.score} />
              <div style={{ flex: 1 }}>
                <Componente nombre="renta" valor={idx.componentes.renta} />
                <Componente nombre="empleo" valor={idx.componentes.paro} />
                <Componente nombre="asequibilidad" valor={idx.componentes.alquiler} />
                <Componente nombre="vitalidad" valor={idx.componentes.envejecimiento} />
                <Componente nombre="servicios" valor={idx.componentes.servicios} />
              </div>
            </div>
          </>
        )}

        {pred && (
          <>
            <h3>Predicción a {pred.anio_horizonte}</h3>
            <div>
              <strong style={{ color: pred.cambio_pct >= 0 ? "#15803d" : "#b91c1c", fontSize: 15 }}>
                {pred.cambio_pct >= 0 ? "+" : ""}{pred.cambio_pct}%
              </strong>
              {pred.cambio_inf != null && (
                <span style={{ color: "var(--text-2)" }}> [{pred.cambio_inf}%..{pred.cambio_sup}%]</span>
              )}
              <span style={{ color: "var(--text-2)" }}> → {pred.pob_proyectada.toLocaleString("es")} hab</span>
            </div>
            {pred.drivers && <div style={{ color: "var(--text-2)", fontSize: 11, marginTop: 2 }}>{pred.drivers}</div>}
          </>
        )}

        {ficha.riesgo && (
          <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8, fontSize: 12 }}>
            <span
              style={{
                width: 10, height: 10, borderRadius: "50%", flexShrink: 0,
                background: ficha.riesgo.nivel === "rojo" ? "#b91c1c" : ficha.riesgo.nivel === "ambar" ? "#f59e0b" : "#16a34a",
              }}
            />
            <span style={{ color: "var(--text-2)" }}>
              Riesgo de despoblación{" "}
              <strong style={{ color: "var(--text)" }}>
                {ficha.riesgo.nivel === "rojo" ? "alto" : ficha.riesgo.nivel === "ambar" ? "medio" : "bajo"}
              </strong>{" "}
              ({ficha.riesgo.prob}% de prob. de pérdida fuerte a 5 años)
            </span>
          </div>
        )}

        {ficha.inflexion && (
          <>
            <h3>Punto de inflexión</h3>
            <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.45 }}>
              Su población <strong style={{ color: "var(--text)" }}>{ficha.inflexion.tipo}</strong>{" "}
              en torno a <strong style={{ color: "var(--text)" }}>{ficha.inflexion.anio}</strong>: pasó de{" "}
              {ficha.inflexion.pend_antes} a {ficha.inflexion.pend_despues} hab/año.
            </div>
          </>
        )}

        {(ficha.rendimiento?.residuo != null || ficha.gemelo) && (
          <>
            <h3>Contra pronóstico</h3>
            {ficha.rendimiento?.residuo != null && (
              <div style={{ fontSize: 12, marginBottom: 6 }}>
                {ficha.rendimiento.clasificacion === "sobre" && (
                  <span style={{ color: "#15803d", fontWeight: 600 }}>
                    Crece {ficha.rendimiento.residuo} pp más de lo que sus características predicen.
                  </span>
                )}
                {ficha.rendimiento.clasificacion === "bajo" && (
                  <span style={{ color: "#b91c1c", fontWeight: 600 }}>
                    Crece {Math.abs(ficha.rendimiento.residuo)} pp menos de lo que sus características predicen.
                  </span>
                )}
                {ficha.rendimiento.clasificacion === "esperado" && (
                  <span style={{ color: "var(--text-2)" }}>
                    Evoluciona según lo que sus características predicen ({ficha.rendimiento.residuo >= 0 ? "+" : ""}{ficha.rendimiento.residuo} pp).
                  </span>
                )}
              </div>
            )}
            {ficha.gemelo && ficha.gemelo.divergencia != null && ficha.gemelo.divergencia >= 5 && (
              <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.45 }}>
                Su gemelo estadístico,{" "}
                <button className="chip" onClick={() => onSelect(ficha.gemelo!.cod)} title={ficha.gemelo.provincia}>
                  {ficha.gemelo.nombre}
                </button>{" "}
                — casi idéntico en datos — {(ficha.gemelo.crec_gemelo ?? 0) > (ficha.gemelo.crec_propio ?? 0) ? "creció" : "cayó"} un{" "}
                <strong style={{ color: "var(--text)" }}>
                  {ficha.gemelo.crec_gemelo}%
                </strong>{" "}
                (2020-2025) frente al {ficha.gemelo.crec_propio}% de {ficha.nombre}. Un experimento natural que invita a preguntarse por qué.
              </div>
            )}
          </>
        )}

        {ficha.servicios && (
          <>
            <h3>Servicios (OSM)</h3>
            <div style={{ display: "flex", gap: 14, color: "var(--text-2)", fontSize: 12, alignItems: "center" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Stethoscope size={13} strokeWidth={1.75} /> {ficha.servicios.salud ?? 0}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <GraduationCap size={13} strokeWidth={1.75} /> {ficha.servicios.educacion ?? 0}
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <ShoppingCart size={13} strokeWidth={1.75} /> {ficha.servicios.comercio ?? 0}
              </span>
              <span style={{ marginLeft: "auto", opacity: 0.8 }}>total {ficha.servicios.total ?? 0}</span>
            </div>
          </>
        )}
        {ficha.aislamiento && (ficha.aislamiento.km_salud ?? 0) > 0 && (
          <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 4 }}>
            Sanidad más cercana a {ficha.aislamiento.km_salud} km
            {ficha.aislamiento.km_capital != null && <> · capital a {ficha.aislamiento.km_capital} km</>}
          </div>
        )}

        {ficha.arquetipo && (
          <div style={{ marginTop: 14 }}>
            <span className="chip" style={{ cursor: "default", background: "var(--bg)", color: "var(--text-2)" }}>
              Arquetipo #{ficha.arquetipo.cluster}: {ficha.arquetipo.etiqueta}
            </span>
          </div>
        )}

        {ficha.similares.length > 0 && (
          <>
            <h3>Pueblos como {ficha.nombre}</h3>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {ficha.similares.map((s) => (
                <button key={s.cod} className="chip" onClick={() => onSelect(s.cod)} title={s.provincia}>
                  {s.nombre}
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
