import type { FichaData, SerieRow } from "../types";
import { colorDeTono, type Tono } from "../veredicto";

const W = 340, H = 170, PAD_X = 8, PAD_TOP = 26, PAD_BOT = 22;

/** El gráfico único que fusiona evolución histórica, predicción con su banda de
 * incertidumbre y el punto de inflexión. Antes eran tres secciones sueltas de la ficha.
 *
 * El color de la línea de proyección lo decide `tono` (calculado por `veredicto()`),
 * no este componente: así el gráfico y el titular nunca pueden contradecirse sobre si
 * hay que afirmar una dirección.
 *
 * **No dibuja la proyección cohorte-componente.** Se probó y el resultado engañaba: su
 * horizonte está fijado en el código (`loaders.py::_HORIZONTE = 2037`, con `anio_base`
 * también fijo) mientras que el del modelo estadístico se deriva cada año de la
 * cobertura real (aquí, 2028). Meter los dos puntos en el mismo eje temporal produce un
 * hueco vacío de años entre ambos y un punto suelto sin relación visual con la curva —
 * más confuso que informativo. El contraste numérico entre los dos métodos ya se dice
 * en texto (`veredicto().contraste`); ver ESTADO.md, deuda conocida sobre `ANIO_BASE`
 * fijado en los modelos demográficos.
 */
export default function Trayectoria({
  serie,
  prediccion,
  inflexion,
  tono,
}: {
  serie: SerieRow[];
  prediccion: FichaData["prediccion"];
  inflexion?: FichaData["inflexion"];
  tono: Tono;
}) {
  const pts = serie.filter((r) => r.poblacion != null);
  if (pts.length < 2 && !prediccion) return null;

  const tieneBanda = prediccion?.cambio_inf != null && prediccion?.cambio_sup != null;
  const pobInf = tieneBanda ? prediccion!.pob_base * (1 + prediccion!.cambio_inf! / 100) : null;
  const pobSup = tieneBanda ? prediccion!.pob_base * (1 + prediccion!.cambio_sup! / 100) : null;

  const anios = pts.map((r) => r.anio);
  const valores = pts.map((r) => r.poblacion as number);
  if (prediccion) {
    anios.push(prediccion.anio_base, prediccion.anio_horizonte);
    valores.push(prediccion.pob_base, prediccion.pob_proyectada);
  }
  if (pobInf != null) valores.push(pobInf);
  if (pobSup != null) valores.push(pobSup);

  const xmin = Math.min(...anios), xmax = Math.max(...anios);
  const ymin = Math.min(...valores), ymax = Math.max(...valores);
  const sx = (x: number) => PAD_X + ((x - xmin) / (xmax - xmin || 1)) * (W - 2 * PAD_X);
  const sy = (y: number) => H - PAD_BOT - ((y - ymin) / (ymax - ymin || 1)) * (H - PAD_TOP - PAD_BOT);

  const dHist = pts.map((r, i) => `${i === 0 ? "M" : "L"}${sx(r.anio)},${sy(r.poblacion as number)}`).join(" ");
  const areaHist =
    pts.length > 1
      ? `${dHist} L${sx(pts[pts.length - 1].anio)},${H - PAD_BOT} L${sx(pts[0].anio)},${H - PAD_BOT} Z`
      : null;

  const color = colorDeTono(tono);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ display: "block", width: "100%" }}>
      {areaHist && <path d={areaHist} fill="var(--accent-soft)" />}
      {pts.length > 1 && <path d={dHist} fill="none" stroke="var(--accent)" strokeWidth={1.5} />}

      {prediccion && (
        <>
          {/* frontera dato medido ←|→ modelo */}
          <line
            x1={sx(prediccion.anio_base)} x2={sx(prediccion.anio_base)}
            y1={PAD_TOP - 6} y2={H - PAD_BOT}
            stroke="var(--border)" strokeWidth={1} strokeDasharray="2 2"
          />

          {tieneBanda && pobInf != null && pobSup != null && (
            <path
              d={
                `M${sx(prediccion.anio_base)},${sy(prediccion.pob_base)} ` +
                `L${sx(prediccion.anio_horizonte)},${sy(pobSup)} ` +
                `L${sx(prediccion.anio_horizonte)},${sy(pobInf)} Z`
              }
              fill="var(--border)"
              fillOpacity={0.4}
            />
          )}

          <line
            x1={sx(prediccion.anio_base)} y1={sy(prediccion.pob_base)}
            x2={sx(prediccion.anio_horizonte)} y2={sy(prediccion.pob_proyectada)}
            stroke={color} strokeWidth={1.75} strokeDasharray="4 3"
          />
          <circle cx={sx(prediccion.anio_horizonte)} cy={sy(prediccion.pob_proyectada)} r={2.75} fill={color} />
        </>
      )}

      {inflexion && (
        <>
          <line
            x1={sx(inflexion.anio)} x2={sx(inflexion.anio)}
            y1={PAD_TOP} y2={H - PAD_BOT}
            stroke="var(--text-2)" strokeWidth={1} strokeOpacity={0.3}
          />
          <text x={sx(inflexion.anio)} y={PAD_TOP - 10} fontSize={9} fill="var(--text-2)" textAnchor="middle">
            {inflexion.tipo} · {inflexion.anio}
          </text>
        </>
      )}

      <text x={PAD_X} y={H - 4} fontSize={9} fill="var(--text-2)">{xmin}</text>
      <text x={W - PAD_X} y={H - 4} fontSize={9} fill="var(--text-2)" textAnchor="end">{xmax}</text>
    </svg>
  );
}
