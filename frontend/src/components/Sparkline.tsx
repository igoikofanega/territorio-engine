import type { SerieRow } from "../types";

export default function Sparkline({ serie }: { serie: SerieRow[] }) {
  const pts = serie.filter((r) => r.poblacion != null);
  if (pts.length < 2) return null;
  const w = 320, h = 64, padX = 4, padTop = 16, padBot = 14;
  const xs = pts.map((r) => r.anio);
  const ys = pts.map((r) => r.poblacion as number);
  const xmin = Math.min(...xs), xmax = Math.max(...xs);
  const ymin = Math.min(...ys), ymax = Math.max(...ys);
  const sx = (x: number) => padX + ((x - xmin) / (xmax - xmin || 1)) * (w - 2 * padX);
  const sy = (y: number) => h - padBot - ((y - ymin) / (ymax - ymin || 1)) * (h - padTop - padBot);
  const d = pts.map((r, i) => `${i === 0 ? "M" : "L"}${sx(r.anio)},${sy(r.poblacion as number)}`).join(" ");
  const area = `${d} L${sx(xmax)},${h - padBot} L${sx(xmin)},${h - padBot} Z`;
  const fin = pts[pts.length - 1];
  const finY = sy(fin.poblacion as number);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ display: "block", width: "100%" }}>
      <path d={area} fill="var(--accent-soft)" />
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth={1.5} />
      <circle cx={sx(fin.anio)} cy={finY} r={2.5} fill="var(--accent)" />
      <text x={w - padX} y={Math.max(11, finY - 6)} fontSize={10} fontWeight={600} fill="var(--text)" textAnchor="end">
        {(fin.poblacion as number).toLocaleString("es")}
      </text>
      <text x={padX} y={h - 2} fontSize={9} fill="var(--text-2)">{xmin}</text>
      <text x={w - padX} y={h - 2} fontSize={9} fill="var(--text-2)" textAnchor="end">{xmax}</text>
    </svg>
  );
}
