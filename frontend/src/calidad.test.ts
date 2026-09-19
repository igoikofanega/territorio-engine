import { describe, expect, it } from "vitest";

import { notaRenta } from "./calidad";
import type { SerieRow } from "./types";

/** Fila de serie con todo a null salvo lo que el test necesita. */
function fila(anio: number, o: Partial<SerieRow> = {}): SerieRow {
  return {
    anio,
    poblacion: null,
    paro: null,
    renta: null,
    alquiler: null,
    temp: null,
    precip: null,
    pct_extranjeros: null,
    renta_secreto: null,
    renta_asignada: null,
    paro_meses: null,
    ...o,
  };
}

describe("notaRenta: la renta que asigna el INE a los municipios de menos de 100 hab.", () => {
  it("desde 2022 dice que es la media de su comarca y no compara con el año anterior", () => {
    // Caso real: Abáigar, 74 habitantes, 18.318 € en 2023 como otros 21 municipios.
    const r = notaRenta([
      fila(2022, { renta: 17221, renta_asignada: true }),
      fila(2023, { renta: 18318, renta_asignada: true }),
    ]);
    expect(r?.nota).toContain("comarca");
    expect(r?.nota).toContain("INE");
    expect(r?.mostrarDelta).toBe(false);
  });

  it("en 2020 y 2021 la media es de su provincia, no de su comarca", () => {
    const r = notaRenta([fila(2021, { renta: 15444, renta_asignada: true })]);
    expect(r?.nota).toContain("provincia");
    expect(r?.nota).not.toContain("comarca");
  });

  it("si el año anterior era asignado, la variación no significa nada", () => {
    // Un municipio que pasa de 99 a 101 habitantes: su dato propio frente a una media.
    const r = notaRenta([
      fila(2022, { renta: 17221, renta_asignada: true }),
      fila(2023, { renta: 19000, renta_asignada: false }),
    ]);
    expect(r?.nota).toBeUndefined();
    expect(r?.mostrarDelta).toBe(false);
  });
});

describe("notaRenta: casos que ya existían", () => {
  it("mantiene el aviso de secreto estadístico si algún año se enmascaró", () => {
    const r = notaRenta([fila(2018, { renta_secreto: true }), fila(2023, { renta: 20000 })]);
    expect(r?.nota).toContain("secreto estadístico");
    expect(r?.mostrarDelta).toBe(true);
  });

  it("un dato propio y limpio va sin nota y con variación", () => {
    const r = notaRenta([fila(2022, { renta: 19000 }), fila(2023, { renta: 20000 })]);
    expect(r).toEqual({ nota: undefined, mostrarDelta: true });
  });

  it("sin renta no hay tarjeta que anotar", () => {
    expect(notaRenta([fila(2023)])).toBeNull();
  });
});
