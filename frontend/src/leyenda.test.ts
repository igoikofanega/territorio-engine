import { describe, expect, it } from "vitest";

import { etiquetasRango } from "./leyenda";

// Misma forma que la escala real "cambio a 2028" (escalas.ts::FUT_BUCKETS): 6 cortes,
// asimétricos, con positivos y negativos. No se importa la constante privada de
// escalas.ts a propósito: esto prueba la lógica de rangos en sí, no un dato concreto.
const CAMBIO_POBLACION: [number, string][] = [
  [20, "#08519c"], [5, "#3182bd"], [0, "#6baed6"], [-10, "#fc8d59"], [-20, "#d7301f"], [-100, "#990000"],
];

describe("etiquetasRango", () => {
  // `color()` (escalas.ts) recorre los buckets de mayor a menor umbral y devuelve el
  // primero con v >= umbral: el corte de cada fila es su cota INFERIOR, no un valor
  // aislado. La leyenda anterior escribía "≥ umbral" en las seis filas por igual, así
  // que la última clase de "cambio a 2028" se leía "≥ -100%" cuando su significado real
  // es "por debajo de -20%" — cierto, pero ilegible sin conocer el código.
  it("la primera fila es un mínimo abierto por arriba", () => {
    const out = etiquetasRango(CAMBIO_POBLACION, "%");
    expect(out[0]).toBe("≥ 20%");
  });

  it("la última fila es un máximo abierto por abajo, no '≥' del último umbral", () => {
    const out = etiquetasRango(CAMBIO_POBLACION, "%");
    expect(out[out.length - 1]).toBe("< -20%");
    expect(out[out.length - 1]).not.toContain("-100");
  });

  it("las filas del medio son rangos [umbral, umbral_anterior)", () => {
    const out = etiquetasRango(CAMBIO_POBLACION, "%");
    expect(out[1]).toBe("5% – 20%");
    expect(out[2]).toBe("0% – 5%");
  });

  it("el sufijo se aplica a los dos extremos del rango", () => {
    const out = etiquetasRango([[100, "#000"], [0, "#fff"]], " km");
    expect(out).toEqual(["≥ 100 km", "< 100 km"]);
  });

  it("sin sufijo no deja un espacio suelto", () => {
    const out = etiquetasRango([[10, "#000"], [0, "#fff"]], "");
    expect(out).toEqual(["≥ 10", "< 10"]);
  });
});
