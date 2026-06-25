import { useEffect, useState } from "react";

const API = "http://localhost:8000";

export default function App() {
  const [apiStatus, setApiStatus] = useState<string>("…");

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((d) => setApiStatus(d.status))
      .catch(() => setApiStatus("sin conexión"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem", lineHeight: 1.5 }}>
      <h1>territorio-engine</h1>
      <p>
        <em>¿Hacia dónde va este pueblo?</em> — esqueleto en marcha.
      </p>
      <p>
        Estado de la API: <strong>{apiStatus}</strong>
      </p>
      <p style={{ color: "#666" }}>
        Próximo paso: modelo de datos (matriz municipio×año) y mapa coroplético.
      </p>
    </main>
  );
}
