import { ArrowUpRight, GitFork, Siren, Sparkles, TrendingDown, Trophy } from "lucide-react";
import { useEffect, useState } from "react";

import { COLOR_CRECE, COLOR_DECAE, RIESGO_COLORES } from "../escalas";
import { resumenAgregado, type VeredictosAgregados } from "../veredicto";

const API = "/api";

type RankItem = { cod: string; nombre: string; valor: number };
type Resumen = {
  ambito: string;
  n_municipios: number;
  poblacion: number | null;
  indice_medio: number | null;
  extranjeros_medio: number | null;
  riesgo: { verde: number; ambar: number; rojo: number };
  giros: { remonta: number; se_hunde: number };
  veredictos: VeredictosAgregados;
  distribucion_indice: { tramo: number; n: number }[];
  rankings: {
    mejor_indice: RankItem[];
    mayor_riesgo: RankItem[];
    mas_crecen: RankItem[];
    mas_caen: RankItem[];
    mas_divergen: RankItem[];
    remontan: RankItem[];
  };
};

function KpiGrande({ label, valor, sub }: { label: string; valor: string; sub?: string }) {
  return (
    <div className="stat-card" style={{ padding: "12px 14px" }}>
      <div className="stat-label">{label}</div>
      <div className="stat-valor" style={{ fontSize: 24 }}>{valor}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Ranking({
  titulo,
  icono: Icono,
  items,
  fmt,
  colorValor = "var(--accent)",
  onSelect,
}: {
  titulo: string;
  icono: typeof Trophy;
  items: RankItem[];
  fmt: (v: number) => string;
  colorValor?: string;
  onSelect: (cod: string) => void;
}) {
  return (
    <div className="panel" style={{ padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
        <Icono size={15} strokeWidth={1.75} style={{ color: "var(--accent)" }} />
        <strong style={{ fontSize: 13 }}>{titulo}</strong>
      </div>
      {items.map((r, i) => (
        <button
          key={r.cod}
          onClick={() => onSelect(r.cod)}
          style={{ display: "flex", width: "100%", alignItems: "baseline", gap: 8, padding: "5px 0", border: 0, borderTop: i ? "1px solid var(--border)" : 0, background: "transparent", cursor: "pointer", font: "inherit", textAlign: "left" }}
        >
          <span style={{ width: 16, color: "var(--text-2)", fontSize: 11 }}>{i + 1}.</span>
          <span style={{ flex: 1, fontSize: 13 }}>{r.nombre}</span>
          <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums", color: colorValor }}>{fmt(r.valor)}</span>
        </button>
      ))}
      {items.length === 0 && <div style={{ fontSize: 12, color: "var(--text-2)" }}>Sin datos.</div>}
    </div>
  );
}

/** La respuesta agregada a la pregunta bandera, para el ámbito entero: cuántos
 * municipios crecen, cuántos se vacían y cuántos son inciertos, con la misma
 * gramática de color que la ficha de un municipio suelto (`veredicto.ts::colorDeTono`)
 * — así "azul" significa lo mismo en el mapa, en la ficha y aquí.
 *
 * La barra no es un adorno: es la forma de ver de un vistazo lo que la frase dice en
 * palabras. Con el caso real de Navarra (76% incierto, 0% "se vacía" con certeza), una
 * barra casi entera gris cuenta la historia más rápido que cualquier número suelto.
 */
function VeredictoAgregado({ v, ambito }: { v: VeredictosAgregados; ambito: string }) {
  const total = v.crece + v.se_vacia + v.incierto + v.sin_datos || 1;
  return (
    <div className="panel" style={{ padding: 16, marginBottom: 18 }}>
      <p style={{ margin: "0 0 10px", fontSize: 14, lineHeight: 1.45, fontWeight: 600 }}>
        {resumenAgregado(v, ambito)}
      </p>
      <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden" }}>
        {v.crece > 0 && (
          <div style={{ width: `${(v.crece / total) * 100}%`, background: COLOR_CRECE }} title={`${v.crece} crecen`} />
        )}
        {v.incierto > 0 && (
          <div style={{ width: `${(v.incierto / total) * 100}%`, background: "var(--border)" }} title={`${v.incierto} inciertos`} />
        )}
        {v.se_vacia > 0 && (
          <div style={{ width: `${(v.se_vacia / total) * 100}%`, background: COLOR_DECAE }} title={`${v.se_vacia} se vacían`} />
        )}
        {v.sin_datos > 0 && (
          <div style={{ width: `${(v.sin_datos / total) * 100}%`, background: "var(--panel-alt)" }} title={`${v.sin_datos} sin datos`} />
        )}
      </div>
      <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--text-2)", marginTop: 8 }}>
        <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: COLOR_CRECE, marginRight: 4 }} />crece</span>
        <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "var(--border)", marginRight: 4 }} />incierto</span>
        <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: COLOR_DECAE, marginRight: 4 }} />se vacía</span>
        {v.sin_datos > 0 && (
          <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "var(--panel-alt)", border: "1px solid var(--border)", marginRight: 4 }} />sin datos</span>
        )}
      </div>
    </div>
  );
}

export default function Dashboard({ prov, ambitoNombre, onSelect }: { prov: string; ambitoNombre: string; onSelect: (cod: string) => void }) {
  const [d, setD] = useState<Resumen | null>(null);

  useEffect(() => {
    setD(null);
    fetch(`${API}/resumen?prov=${prov}`).then((r) => r.json()).then(setD).catch(() => setD(null));
  }, [prov]);

  if (!d) return <div style={{ padding: 40, color: "var(--text-2)" }}>Cargando resumen de {ambitoNombre}…</div>;

  const totalRiesgo = d.riesgo.verde + d.riesgo.ambar + d.riesgo.rojo || 1;
  const maxTramo = Math.max(...d.distribucion_indice.map((t) => t.n), 1);

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: 24, background: "var(--bg)" }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", margin: "0 0 2px" }}>{d.ambito}</h1>
      <div style={{ color: "var(--text-2)", fontSize: 13, marginBottom: 18 }}>
        Radiografía territorial · {d.n_municipios.toLocaleString("es")} municipios
      </div>

      <VeredictoAgregado v={d.veredictos} ambito={d.ambito} />

      {/* KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 18 }}>
        <KpiGrande label="Población" valor={(d.poblacion ?? 0).toLocaleString("es")} sub="último padrón" />
        <KpiGrande label="Índice medio" valor={d.indice_medio != null ? `${d.indice_medio}/100` : "—"} sub="¿dónde vivir?" />
        <KpiGrande label="Extranjeros" valor={d.extranjeros_medio != null ? `${d.extranjeros_medio}%` : "—"} sub="media municipal" />
        <KpiGrande label="Remontan" valor={d.giros.remonta.toLocaleString("es")} sub={`vs ${d.giros.se_hunde} que se hunden`} />
      </div>

      {/* riesgo + distribución */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 18 }}>
        <div className="panel" style={{ padding: 14 }}>
          <strong style={{ fontSize: 13 }}>Riesgo de despoblación fuerte</strong>
          <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", margin: "10px 0 8px" }}>
            <div style={{ width: `${(d.riesgo.verde / totalRiesgo) * 100}%`, background: RIESGO_COLORES.verde }} />
            <div style={{ width: `${(d.riesgo.ambar / totalRiesgo) * 100}%`, background: RIESGO_COLORES.ambar }} />
            <div style={{ width: `${(d.riesgo.rojo / totalRiesgo) * 100}%`, background: RIESGO_COLORES.rojo }} />
          </div>
          <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--text-2)" }}>
            <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: RIESGO_COLORES.verde, marginRight: 4 }} />{d.riesgo.verde} bajo</span>
            <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: RIESGO_COLORES.ambar, marginRight: 4 }} />{d.riesgo.ambar} medio</span>
            <span><span style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: RIESGO_COLORES.rojo, marginRight: 4 }} />{d.riesgo.rojo} alto</span>
          </div>
        </div>
        <div className="panel" style={{ padding: 14 }}>
          <strong style={{ fontSize: 13 }}>Distribución del índice</strong>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 60, marginTop: 10 }}>
            {[1, 2, 3, 4, 5].map((tr) => {
              const n = d.distribucion_indice.find((t) => t.tramo === tr)?.n ?? 0;
              return (
                <div key={tr} style={{ flex: 1, textAlign: "center" }}>
                  <div style={{ height: `${(n / maxTramo) * 48}px`, background: "var(--accent)", borderRadius: "3px 3px 0 0", opacity: 0.35 + 0.13 * tr }} title={`${n} municipios`} />
                  <div style={{ fontSize: 9, color: "var(--text-2)", marginTop: 3 }}>{(tr - 1) * 20}-{tr * 20}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* rankings */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
        <Ranking titulo="Mejor para vivir" icono={Trophy} items={d.rankings.mejor_indice} fmt={(v) => `${v}`} onSelect={onSelect} />
        <Ranking titulo="Mayor crecimiento previsto" icono={Sparkles} items={d.rankings.mas_crecen} fmt={(v) => `${v >= 0 ? "+" : ""}${v}%`} colorValor={COLOR_CRECE} onSelect={onSelect} />
        <Ranking titulo="Mayor caída prevista" icono={TrendingDown} items={d.rankings.mas_caen} fmt={(v) => `${v}%`} colorValor={COLOR_DECAE} onSelect={onSelect} />
        <Ranking titulo="Han remontado" icono={ArrowUpRight} items={d.rankings.remontan} fmt={(v) => `${v}`} onSelect={onSelect} />
        <Ranking titulo="Mayor riesgo" icono={Siren} items={d.rankings.mayor_riesgo} fmt={(v) => `${v}%`} onSelect={onSelect} />
        <Ranking
          titulo="Gemelos más divergentes"
          icono={GitFork}
          items={d.rankings.mas_divergen}
          fmt={(v) => `${v.toFixed(1)} pp`}
          onSelect={onSelect}
        />
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 14, fontSize: 11, color: "var(--text-2)" }}>
        <TrendingDown size={12} /> "Han remontado" muestra el año del giro; "gemelos" muestra cuánto diverge cada
        municipio del suyo. El resto, el valor del indicador.
      </div>
    </div>
  );
}
