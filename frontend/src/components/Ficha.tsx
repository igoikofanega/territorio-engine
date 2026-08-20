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
  Wifi,
  X,
} from "lucide-react";

import { COLOR_CRECE, COLOR_DECAE, RIESGO_COLORES } from "../escalas";
import { etiquetaArquetipo, parsearDrivers } from "../motivos";
import type { FichaData, NoticiasData, SerieRow } from "../types";
import { veredicto } from "../veredicto";
import BarraDivergente from "./BarraDivergente";
import Drivers from "./Drivers";
import Escenarios from "./Escenarios";
import Seccion from "./Seccion";
import Trayectoria from "./Trayectoria";

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

/** Panel de prensa local.
 *
 * Distingue tres estados que la interfaz NO debe confundir: fuera del ámbito de la capa
 * (no se ha preguntado), dentro pero sin titulares (se preguntó y no hay), y con
 * titulares. Un municipio de Cuenca no es un municipio del que no se habla: es uno que
 * esta capa no cubre. Ver docs/adr/0005-capa-de-noticias-y-llm.md.
 *
 * Sin cabecera propia: quien lo envuelve (`Seccion`) ya pone el título "Prensa local".
 */
function Noticias({ noticias, nombre }: { noticias: NoticiasData; nombre: string }) {
  if (!noticias.consultado) {
    return (
      <div style={{ fontSize: 11, color: "var(--text-2)", lineHeight: 1.45 }}>
        Capa regional: la prensa solo está indexada en {noticias.ambito}. No hay dato para{" "}
        {nombre}, que no es lo mismo que no salir en la prensa.
      </div>
    );
  }

  if (!noticias.noticias.length) {
    return (
      <div style={{ fontSize: 11, color: "var(--text-2)" }}>Sin titulares indexados en GDELT (2017→).</div>
    );
  }

  // El color solo marca el signo cuando lo hay; el gris es "neutro o sin clasificar",
  // no un tercer juicio.
  const color = (signo: number | null) =>
    signo == null || signo === 0 ? "var(--border)" : signo > 0 ? COLOR_CRECE : COLOR_DECAE;

  return (
    <>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
        {noticias.noticias.map((n) => (
          <li key={n.url} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <span
              style={{ width: 5, height: 5, borderRadius: 999, background: color(n.signo), marginTop: 6, flexShrink: 0 }}
            />
            <div style={{ minWidth: 0 }}>
              <a
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12, lineHeight: 1.35, color: "var(--text)", textDecoration: "none" }}
              >
                {n.titular}
              </a>
              <div style={{ fontSize: 10, color: "var(--text-2)", marginTop: 1 }}>
                {n.medio}
                {n.fecha && <> · {n.fecha}</>}
                {n.tema && <> · {n.tema}</>}
              </div>
            </div>
          </li>
        ))}
      </ul>
      <div style={{ fontSize: 10, color: "var(--text-2)", marginTop: 6 }}>
        Titulares y enlaces de GDELT. El texto completo es de cada medio.
      </div>
    </>
  );
}

export default function Ficha({ ficha, noticias, onClose, onSelect }: { ficha: FichaData | null; noticias: NoticiasData | null; onClose: () => void; onSelect: (cod: string) => void }) {
  if (!ficha) {
    return (
      <div className="ficha" style={{ padding: 16 }}>
        <button className="btn-ghost" onClick={onClose} style={{ float: "right" }}><X size={16} /></button>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 40, color: "var(--text-2)", fontSize: 13 }}>
          <span className="spinner" aria-hidden="true" />
          Cargando la ficha del municipio…
        </div>
      </div>
    );
  }
  const idx = ficha.indice;
  const foto = ficha.wiki?.imagen;
  const v = veredicto(ficha);

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

  // Contenido por bloque: una Seccion sin nada dentro no se renderiza (quedaría un
  // desplegable vacío, que confunde más que ayudar).
  const nDrivers = parsearDrivers(ficha.prediccion?.drivers ?? null).length;
  const porQueTieneContenido = nDrivers > 0 || !!ficha.demografia || ficha.rendimiento?.residuo != null;
  const gemeloDestaca = !!(ficha.gemelo && (ficha.gemelo.divergencia ?? 0) >= 5);
  const nComparables = (gemeloDestaca ? 1 : 0) + ficha.similares.length;
  const comparablesTieneContenido = nComparables > 0;
  const vivirAquiTieneContenido = !!idx || !!renta || !!paroPct || !!alquiler || !!extranjeros;
  const entornoTieneContenido =
    !!ficha.servicios ||
    (ficha.aislamiento?.km_salud ?? 0) > 0 ||
    ficha.conectividad?.pct_fibra != null ||
    ficha.aire?.pm25 != null ||
    ficha.clima?.temp != null;
  const resumenPrensa = noticias
    ? noticias.consultado
      ? `${noticias.noticias.length} titular${noticias.noticias.length === 1 ? "" : "es"}`
      : "fuera del ámbito"
    : null;
  // Escala común para las dos barras del motor demográfico: así se comparan entre sí,
  // no solo contra su propio número.
  const maxSaldo = Math.max(
    Math.abs(ficha.demografia?.saldo_vegetativo ?? 0),
    Math.abs(ficha.demografia?.saldo_migratorio ?? 0),
    1,
  );

  return (
    <div className="ficha">
      {/* cabecera héroe: foto o gradiente del primario. 120px fijo (antes 176 con foto):
          la ficha se abre para responder la pregunta bandera, no para ver una foto. */}
      <div
        style={{
          position: "relative",
          flexShrink: 0,
          height: 120,
          background: foto ? `url(${foto}) center/cover` : "linear-gradient(135deg, #001849, #0050cb)",
        }}
      >
        <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,24,73,0) 30%, rgba(0,24,73,.78))" }} />
        <button
          onClick={onClose}
          style={{ position: "absolute", top: 12, right: 12, color: "white", background: "rgba(255,255,255,.18)", backdropFilter: "blur(4px)", border: 0, width: 30, height: 30, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: 999, cursor: "pointer" }}
        >
          <X size={16} strokeWidth={2} />
        </button>
        <div style={{ position: "absolute", left: 20, right: 20, bottom: 14, color: "white" }}>
          <div style={{ fontFamily: "'Hanken Grotesk', sans-serif", fontSize: 22, fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.1, textShadow: "0 1px 3px rgba(0,0,0,.5)" }}>{ficha.nombre}</div>
          <div style={{ fontSize: 13, opacity: 0.9, marginTop: 2 }}>
            {ficha.provincia.nombre}
            {ficha.wiki?.gentilicio ? ` · ${ficha.wiki.gentilicio}` : ""}
            {ficha.superficie_km2 ? ` · ${ficha.superficie_km2.toFixed(1)} km²` : ""}
            {ficha.wiki?.altitud ? ` · ${Math.round(ficha.wiki.altitud)} m` : ""}
          </div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0 20px 20px" }}>
        {/* identidad: descripción breve (dos líneas), población y arquetipo */}
        {ficha.wiki?.descripcion && (
          <p
            style={{
              margin: "14px 0 8px", lineHeight: 1.4, fontSize: 12, color: "var(--text-2)",
              display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
            }}
          >
            {ficha.wiki.descripcion}
          </p>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginTop: ficha.wiki?.descripcion ? 0 : 14, marginBottom: 16 }}>
          {pob && (
            <span style={{ fontSize: 13 }}>
              <span className="mono" style={{ fontWeight: 700 }}>{pob.valor.toLocaleString("es")}</span>{" "}
              <span style={{ color: "var(--text-2)" }}>hab. ({pob.anio})</span>
            </span>
          )}
          {ficha.arquetipo && (
            <span
              className="chip"
              style={{ cursor: "default", background: "var(--bg)", color: "var(--text-2)" }}
              title={`Arquetipo #${ficha.arquetipo.cluster}: ${ficha.arquetipo.etiqueta}`}
            >
              {etiquetaArquetipo(ficha.arquetipo.etiqueta)}
            </span>
          )}
        </div>

        {/* veredicto: la pregunta bandera del proyecto, siempre visible */}
        <div style={{ paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
          <p style={{ margin: "0 0 4px", fontSize: 14, lineHeight: 1.45, fontWeight: 600, color: v.tono === "sin-datos" ? "var(--text-2)" : v.tono === "incierto" ? "var(--text)" : v.tono === "crece" ? COLOR_CRECE : COLOR_DECAE }}>
            {v.titular}
          </p>
          {v.contraste && (
            <p style={{ margin: "0 0 10px", fontSize: 11, color: "var(--text-2)", lineHeight: 1.4 }}>{v.contraste}</p>
          )}
          {v.confianza && (v.tono === "crece" || v.tono === "se-vacia") && (
            <div className="label-caps" style={{ fontSize: 9, marginBottom: 10 }}>Confianza {v.confianza}</div>
          )}
          <Trayectoria serie={ficha.serie} prediccion={ficha.prediccion} inflexion={ficha.inflexion} tono={v.tono} />
          {ficha.riesgo && (
            <div style={{ marginTop: 14 }}>
              <Escenarios riesgo={ficha.riesgo} nombre={ficha.nombre} horizonteAnios={ficha.prediccion ? ficha.prediccion.anio_horizonte - ficha.prediccion.anio_base : undefined} />
            </div>
          )}
        </div>

        {porQueTieneContenido && (
          <Seccion titulo="Por qué" abierta>
            {nDrivers > 0 && <Drivers drivers={ficha.prediccion?.drivers ?? null} />}
            {ficha.demografia && (
              <div style={{ marginTop: nDrivers > 0 ? 14 : 0 }}>
                <div style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 6 }}>
                  Motor demográfico: <span style={{ textTransform: "capitalize" }}>{ficha.demografia.tipo}</span>
                </div>
                <BarraDivergente etiqueta="Vegetativo" valor={ficha.demografia.saldo_vegetativo} max={maxSaldo} estimado />
                <BarraDivergente etiqueta="Migratorio" valor={ficha.demografia.saldo_migratorio} max={maxSaldo} />
              </div>
            )}
            {ficha.rendimiento?.residuo != null && (
              <div style={{ fontSize: 12, marginTop: 14 }}>
                {ficha.rendimiento.clasificacion === "sobre" && (
                  <span style={{ color: COLOR_CRECE, fontWeight: 600 }}>
                    Crece {ficha.rendimiento.residuo} pp más de lo que sus características predicen.
                  </span>
                )}
                {ficha.rendimiento.clasificacion === "bajo" && (
                  <span style={{ color: COLOR_DECAE, fontWeight: 600 }}>
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
          </Seccion>
        )}

        {comparablesTieneContenido && (
          <Seccion titulo="Comparables" resumen={`${nComparables} pueblo${nComparables === 1 ? "" : "s"}`}>
            {gemeloDestaca && ficha.gemelo && (
              <div style={{ fontSize: 12, color: "var(--text-2)", lineHeight: 1.45, marginBottom: ficha.similares.length ? 12 : 0 }}>
                Su gemelo estadístico,{" "}
                <button className="chip" onClick={() => onSelect(ficha.gemelo!.cod)} title={ficha.gemelo.provincia}>
                  {ficha.gemelo.nombre}
                </button>{" "}
                — casi idéntico en datos — {(ficha.gemelo.crec_gemelo ?? 0) > (ficha.gemelo.crec_propio ?? 0) ? "creció" : "cayó"} un{" "}
                <strong style={{ color: "var(--text)" }}>{ficha.gemelo.crec_gemelo}%</strong>{" "}
                (2020-2025) frente al {ficha.gemelo.crec_propio}% de {ficha.nombre}. Un experimento natural que invita a preguntarse por qué.
              </div>
            )}
            {ficha.similares.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {ficha.similares.map((s) => (
                  <button key={s.cod} className="chip" onClick={() => onSelect(s.cod)} title={s.provincia}>
                    {s.nombre}
                  </button>
                ))}
              </div>
            )}
          </Seccion>
        )}

        {vivirAquiTieneContenido && (
          <Seccion titulo="Vivir aquí" resumen={idx?.score != null ? `${idx.score}/100` : null}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: idx ? 14 : 0 }}>
              {renta && (
                <StatCard icono={Wallet} label="Renta" anio={renta.anio} valor={Math.round(renta.valor).toLocaleString("es")} unidad="€/pers" delta={deltaPct(renta)} />
              )}
              {paroPct && <StatCard icono={Briefcase} label="Paro" anio={paroPct.anio} valor={paroPct.valor.toFixed(0)} unidad="‰ hab" />}
              {alquiler && (
                <StatCard icono={Home} label="Alquiler" anio={alquiler.anio} valor={alquiler.valor.toFixed(1)} unidad="€/m²" delta={deltaPct(alquiler)} />
              )}
              {extranjeros && (
                <StatCard icono={UsersRound} label="Extranjeros" anio={extranjeros.anio} valor={extranjeros.valor.toFixed(1)} unidad="%" delta={deltaPct(extranjeros)} />
              )}
            </div>
            {idx && (
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
            )}
          </Seccion>
        )}

        {entornoTieneContenido && (
          <Seccion titulo="Entorno">
            {ficha.servicios && (
              <div style={{ display: "flex", gap: 14, color: "var(--text-2)", fontSize: 12, alignItems: "center", marginBottom: 10 }}>
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
            )}
            {(ficha.aislamiento?.km_salud ?? 0) > 0 && (
              <div style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 10 }}>
                Sanidad más cercana a {ficha.aislamiento!.km_salud} km
                {ficha.aislamiento!.km_capital != null && <> · capital a {ficha.aislamiento!.km_capital} km</>}
              </div>
            )}
            {ficha.conectividad?.pct_fibra != null && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 14px", fontSize: 12, color: "var(--text-2)", marginBottom: 10 }}>
                <span><Wifi size={12} strokeWidth={1.75} style={{ verticalAlign: "-1px" }} /> {ficha.conectividad.pct_fibra}% fibra</span>
                {ficha.conectividad.pct_100mbps != null && <span>· {ficha.conectividad.pct_100mbps}% ≥100 Mbps</span>}
                {ficha.conectividad.pct_5g != null && <span>· {ficha.conectividad.pct_5g}% 5G</span>}
              </div>
            )}
            {ficha.aire?.pm25 != null && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 6 }}>
                <span
                  style={{
                    width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
                    background: ficha.aire.pm25 <= 5 ? RIESGO_COLORES.verde : ficha.aire.pm25 <= 10 ? RIESGO_COLORES.ambar : RIESGO_COLORES.rojo,
                  }}
                />
                <span style={{ color: "var(--text-2)" }}>
                  PM2.5 <strong style={{ color: "var(--text)" }}>{ficha.aire.pm25} µg/m³</strong>{" "}
                  <span style={{ fontSize: 10 }}>(guía OMS: ≤5)</span>
                </span>
              </div>
            )}
            {ficha.clima?.temp != null && (
              <div style={{ fontSize: 12, color: "var(--text-2)" }}>
                {ficha.clima.temp} °C media
                {ficha.clima.dias_despejados != null && <> · {ficha.clima.dias_despejados} días despejados/año</>}
              </div>
            )}
          </Seccion>
        )}

        {noticias && (
          <Seccion titulo="Prensa local" resumen={resumenPrensa}>
            <Noticias noticias={noticias} nombre={ficha.nombre} />
          </Seccion>
        )}
      </div>
    </div>
  );
}
