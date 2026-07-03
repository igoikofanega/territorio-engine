import { useEffect, useState } from "react";

import type { Sugerencia } from "../types";

const API = "/api";

export default function Buscador({ onSelect }: { onSelect: (cod: string) => void }) {
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
    <div style={{ position: "relative" }}>
      <input
        className="input"
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
      />
      {abierto && items.length > 0 && (
        <ul className="panel" style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, margin: 0, padding: 4, listStyle: "none", maxHeight: 280, overflowY: "auto", zIndex: 1200 }}>
          {items.map((s, i) => (
            <li
              key={s.cod}
              onMouseDown={() => pick(s)}
              onMouseEnter={() => setCursor(i)}
              style={{ padding: "6px 8px", cursor: "pointer", borderRadius: 4, background: i === cursor ? "var(--accent-soft)" : "transparent", fontSize: 12 }}
            >
              <strong>{s.nombre}</strong>
              <span style={{ color: "var(--text-2)" }}> · {s.provincia}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
