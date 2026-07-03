import type { SerieRow } from "../types";

export default function Sparkline({ serie }: { serie: SerieRow[] }) {
  const pts = serie.filter((r) => r.poblacion != null);
  if (pts.length < 2) return null;
  const w = 320, h = 56, pad = 4;
  const xs = pts.map((r) => r.anio);
  const ys = pts.map((r) => r.poblacion as number);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = (x: number) => pad + ((x - xmin) / (xmax - xmin || 1)) * (w - 2 * pad);
  const sy = (y: number) => h - pad - ((y - ymin) / (ymax - ymin || 1)) * (h - 2 * pad);
  const d = pts.map((r, i) => `${i === 0 ? "M" : "L"}${sx(r.anio)},${sy(r.poblacion as number)}`).join(" ");
  const area = `${d} L${sx(xmax)},${h - pad} L${sx(xmin)},${h - pad} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ display: "block", width: "100%" }}>
      <path d={area} fill="var(--accent-soft)" />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.5} />
      <text x={pad} y={h - 1} fontSize={9} fill="var(--text-2)">{xmin}</text>
      <text x={w - pad} y={h - 1} fontSize={9} fill="var(--text-2)" textAnchor="end">{xmax}</text>
      <text x={pad} y={10} fontSize={9} fill="var(--text-2)">{ymax.toLocaleString("es")}</text>
    </svg>
  );
}
