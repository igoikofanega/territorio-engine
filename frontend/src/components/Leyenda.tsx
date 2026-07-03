export default function Leyenda({
  titulo,
  buckets,
  categorias,
  nota,
}: {
  titulo: string;
  buckets: [number, string][];
  categorias?: { color: string; label: string }[] | null;
  nota?: string | null;
}) {
  const items = categorias ?? [...buckets].reverse().map(([u, c]) => ({ color: c, label: `≥ ${u.toLocaleString("es")}` }));
  return (
    <div className="panel" style={{ position: "absolute", bottom: 20, right: 16, zIndex: 1000, padding: "10px 12px", fontSize: 12, maxWidth: 220 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>{titulo}</div>
      {items.map((it, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, margin: "2px 0" }}>
          <span style={{ width: 14, height: 14, background: it.color, display: "inline-block", flexShrink: 0, borderRadius: 3 }} />
          <span style={{ color: "var(--text-2)" }}>{it.label}</span>
        </div>
      ))}
      {nota && <div style={{ marginTop: 6, fontSize: 10, color: "var(--accent)" }}>{nota}</div>}
    </div>
  );
}
