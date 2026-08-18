import { describe, expect, it } from "vitest";

import { etiquetaArquetipo, frase, parsearDrivers } from "./motivos";

describe("parsearDrivers", () => {
  it("parsea el formato real de ml/modelo.py::_drivers", () => {
    const d = parsearDrivers("paro↑ · tendencia↓");
    expect(d).toHaveLength(2);
    expect(d[0]).toEqual({ etiqueta: "paro", direccion: "↑", texto: frase("paro", "↑") });
    expect(d[1].etiqueta).toBe("tendencia");
    expect(d[1].direccion).toBe("↓");
  });

  it("una etiqueta de dos palabras se parsea entera", () => {
    const d = parsearDrivers("sanidad lejos↑");
    expect(d[0].etiqueta).toBe("sanidad lejos");
  });

  it("null o vacío no revienta", () => {
    expect(parsearDrivers(null)).toEqual([]);
    expect(parsearDrivers("")).toEqual([]);
  });

  it("una etiqueta desconocida no rompe: cae al texto pelado", () => {
    // Contrato entre servicios: si ml/modelo.py::ETIQUETAS cambia y este diccionario
    // no se actualiza a la vez, una ficha no debe romperse por eso.
    expect(frase("algo-nuevo-que-no-existe-aun", "↑")).toBe("algo-nuevo-que-no-existe-aun");
  });
});

describe("frase: cobertura de las 17 features de ml/features.py::FEATURES", () => {
  // Vía ETIQUETAS (ml/modelo.py): log_pob→tamaño, paro_1000→paro, etc. Si falta una,
  // esa feature aparecería en la ficha como su etiqueta pelada en vez de una frase.
  const etiquetas = [
    "tamaño",
    "densidad",
    "paro",
    "renta",
    "alquiler",
    "envejec.",
    "temp.",
    "lluvia",
    "natalidad",
    "mortalidad",
    "tendencia",
    "sanidad lejos",
    "lejanía",
    "sol",
    "frío",
    "inmigración",
    "fibra",
  ];

  it.each(etiquetas)("'%s' tiene frase para ↑ y para ↓, y son distintas", (etiqueta) => {
    const up = frase(etiqueta, "↑");
    const down = frase(etiqueta, "↓");
    expect(up).not.toBe(etiqueta); // no cae al fallback
    expect(down).not.toBe(etiqueta);
    expect(up).not.toBe(down);
  });
});

describe("etiquetaArquetipo", () => {
  // ml/clustering.py construye la etiqueta del arquetipo con el MISMO formato que los
  // drivers de predicción: sin esto, el chip de arquetipo enseñaba "alquiler↑ ·
  // tamaño↑" tal cual, tan ilegible como lo eran los drivers antes de este bloque.
  it("traduce el formato crudo del backend a frases cortas", () => {
    expect(etiquetaArquetipo("alquiler↑ · tamaño↑")).toBe("alquiler caro · grande");
  });

  it("es corta: cada fragmento son 1-3 palabras, no una frase completa", () => {
    const out = etiquetaArquetipo("paro↑ · tendencia↓");
    for (const frag of out.split(" · ")) {
      expect(frag.split(" ").length).toBeLessThanOrEqual(3);
    }
  });

  it("null o vacío no revienta", () => {
    expect(etiquetaArquetipo(null)).toBe("");
    expect(etiquetaArquetipo("")).toBe("");
  });

  it("una cadena sin el formato esperado se devuelve tal cual", () => {
    expect(etiquetaArquetipo("texto libre sin flechas")).toBe("texto libre sin flechas");
  });
});
