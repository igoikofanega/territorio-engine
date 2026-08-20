import { describe, expect, it } from "vitest";

import type { FichaData } from "./types";
import { resumenAgregado, veredicto } from "./veredicto";

/** Ficha mínima con todo lo demás en null/vacío, para no repetir 20 campos por test. */
function baseFicha(overrides: Partial<FichaData> = {}): FichaData {
  return {
    cod: "31999",
    nombre: "Villaejemplo",
    provincia: { cod: "31", nombre: "Navarra" },
    superficie_km2: 10,
    wiki: null,
    serie: [],
    indice: null,
    prediccion: null,
    arquetipo: null,
    rendimiento: null,
    proyeccion_cohorte: null,
    gemelo: null,
    servicios: null,
    riesgo: null,
    inflexion: null,
    demografia: null,
    aislamiento: null,
    conectividad: null,
    aire: null,
    clima: null,
    similares: [],
    ...overrides,
  };
}

const prediccion = (over: Partial<NonNullable<FichaData["prediccion"]>>) => ({
  anio_base: 2023,
  anio_horizonte: 2028,
  pob_base: 1000,
  pob_proyectada: 950,
  cambio_pct: -5,
  cambio_inf: -8,
  cambio_sup: -2,
  drivers: null,
  ...over,
});

describe("veredicto: la banda que cruza cero nunca es direccional", () => {
  // Esta es LA condición del bloque de veredicto. Sin esta garantía, el producto podría
  // decirle a alguien "tu pueblo se vacía" cuando el modelo, en realidad, no lo sabe.
  it("no dice 'crece' ni 'se vacía' cuando la banda cruza cero", () => {
    const f = baseFicha({
      prediccion: prediccion({ cambio_pct: 2, cambio_inf: -4, cambio_sup: 6 }),
    });
    const v = veredicto(f);
    expect(v.tono).toBe("incierto");
    expect(v.titular.toLowerCase()).not.toContain("se vacía");
    expect(v.titular.toLowerCase()).not.toMatch(/\bcrece\b/);
  });

  it("cruzar cero por muy poco también cuenta (inf negativo, sup positivo)", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_pct: 0.1, cambio_inf: -0.1, cambio_sup: 0.3 }) });
    expect(veredicto(f).tono).toBe("incierto");
  });

  it("una banda que no cruza cero (toda negativa) sí es direccional", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_pct: -5, cambio_inf: -8, cambio_sup: -2 }) });
    const v = veredicto(f);
    expect(v.tono).toBe("se-vacia");
    expect(v.titular).toContain("se vacía");
  });

  it("una banda que no cruza cero (toda positiva) es 'crece'", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_pct: 6, cambio_inf: 3, cambio_sup: 9 }) });
    const v = veredicto(f);
    expect(v.tono).toBe("crece");
    expect(v.titular).toContain("crece");
  });
});

describe("veredicto: sin predicción", () => {
  it("explica el motivo en vez de dejar un hueco", () => {
    const f = baseFicha({ serie: [{ anio: 2023, poblacion: 500, paro: null, renta: 20000, alquiler: null, temp: null, precip: null, pct_extranjeros: null }] });
    const v = veredicto(f);
    expect(v.tono).toBe("sin-datos");
    expect(v.titular).toContain("paro");
    expect(v.titular).toContain("2023");
    expect(v.confianza).toBeNull();
  });

  it("sin serie histórica, no revienta y da un motivo genérico", () => {
    const v = veredicto(baseFicha({ serie: [] }));
    expect(v.tono).toBe("sin-datos");
    expect(v.titular.length).toBeGreaterThan(0);
  });

  it("cuando faltan los tres datos, la lista se escribe en español natural", () => {
    // Caso real: "Comunidad de Bascuñana y Viloria de Rioja" (cod 53015) tiene fila en
    // la serie —temp/precip de AEMET— pero población, paro y renta a null: es una
    // entidad geográfica sin población propia, no un hueco de carga.
    const f = baseFicha({
      serie: [{ anio: 2022, poblacion: null, paro: null, renta: null, alquiler: null, temp: 12.5, precip: 473, pct_extranjeros: null }],
    });
    const v = veredicto(f);
    expect(v.titular).toContain("población, paro y renta");
    expect(v.titular).not.toContain("población y paro y renta");
  });
});

describe("veredicto: contraste con la proyección cohorte-componente (ADR 0004)", () => {
  it("cuando los dos métodos coinciden, el contraste refuerza", () => {
    const f = baseFicha({
      prediccion: prediccion({ cambio_pct: -5, cambio_inf: -8, cambio_sup: -2 }),
      proyeccion_cohorte: { anio_horizonte: 2028, pob_proyectada: 960, cambio_pct: -4, trayectoria: "declive" },
    });
    const v = veredicto(f);
    expect(v.tono).toBe("se-vacia");
    expect(v.contraste).toContain("parecida");
  });

  it("cuando discrepan, el titular pasa a incierto aunque la banda no cruce cero", () => {
    const f = baseFicha({
      prediccion: prediccion({ cambio_pct: -5, cambio_inf: -8, cambio_sup: -2 }),
      proyeccion_cohorte: { anio_horizonte: 2028, pob_proyectada: 1050, cambio_pct: 5, trayectoria: "crecimiento" },
    });
    const v = veredicto(f);
    expect(v.tono).toBe("incierto");
    expect(v.titular.toLowerCase()).not.toContain("se vacía");
    expect(v.contraste).toContain("no coinciden");
  });

  it("sin proyección cohorte, el contraste es null", () => {
    const f = baseFicha({ prediccion: prediccion({}) });
    expect(veredicto(f).contraste).toBeNull();
  });
});

describe("veredicto: confianza según el ancho de la banda", () => {
  it("banda estrecha → confianza alta", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_pct: 3, cambio_inf: 1, cambio_sup: 5 }) });
    expect(veredicto(f).confianza).toBe("alta");
  });

  it("banda ancha → confianza baja", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_pct: 3, cambio_inf: -12, cambio_sup: 18 }) });
    expect(veredicto(f).confianza).toBe("baja");
  });

  it("sin banda (cambio_inf/sup null), confianza es null", () => {
    const f = baseFicha({ prediccion: prediccion({ cambio_inf: null, cambio_sup: null }) });
    expect(veredicto(f).confianza).toBeNull();
  });
});

describe("resumenAgregado", () => {
  it("caso real medido en Navarra: mayoría incierta, cero 'se vacía' con certeza", () => {
    const frase = resumenAgregado({ crece: 65, se_vacia: 0, incierto: 207, sin_datos: 0 }, "Navarra");
    expect(frase).toContain("65 crecen");
    expect(frase).toContain("0 se vacían");
    expect(frase).toContain("207 (76%)");
  });

  it("con sin_datos > 0, se cuentan aparte del total con predicción", () => {
    const frase = resumenAgregado({ crece: 10, se_vacia: 5, incierto: 5, sin_datos: 3 }, "Aragón");
    expect(frase).toContain("De 20 municipios con predicción");
    expect(frase).toContain("3 no tienen predicción");
  });

  it("sin incierto, no menciona la banda de incertidumbre", () => {
    const frase = resumenAgregado({ crece: 10, se_vacia: 0, incierto: 0, sin_datos: 0 }, "X");
    expect(frase).not.toContain("banda de incertidumbre");
  });

  it("ámbito vacío no revienta", () => {
    const frase = resumenAgregado({ crece: 0, se_vacia: 0, incierto: 0, sin_datos: 0 }, "X");
    expect(frase.length).toBeGreaterThan(0);
  });

  it("todos sin datos no revienta (división por cero)", () => {
    const frase = resumenAgregado({ crece: 0, se_vacia: 0, incierto: 0, sin_datos: 8 }, "X");
    expect(frase).toContain("no predice ninguno");
  });
});
