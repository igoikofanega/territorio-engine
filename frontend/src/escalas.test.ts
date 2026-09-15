import { describe, expect, it } from "vitest";

import { ESCALAS, GRUPOS_MODOS, PESOS_DEFECTO, color, combinaCustom } from "./escalas";
import { CLAVES_INDICE, type Modo } from "./types";

// `modos` (siempre visibles) + `secundarios` (plegados, ver Sidebar.tsx): las dos
// cuentan como "alcanzable desde el menú", solo que una está a un clic más.
const modosDeGrupo = (g: (typeof GRUPOS_MODOS)[number]) => [...g.modos, ...(g.secundarios ?? [])];

describe("catálogo de modos", () => {
  // ESCALAS y GRUPOS_MODOS se editan por separado: es fácil añadir un modo a uno
  // y olvidarlo en el otro. El síntoma sería una entrada de menú que no pinta nada,
  // o una capa inalcanzable desde la interfaz.
  it("todo modo del menú (visible o plegado) existe en ESCALAS", () => {
    for (const grupo of GRUPOS_MODOS) {
      for (const modo of modosDeGrupo(grupo)) {
        expect(ESCALAS[modo], `modo "${modo}" del grupo "${grupo.titulo}"`).toBeDefined();
      }
    }
  });

  it("no hay modos duplicados entre grupos", () => {
    const todos = GRUPOS_MODOS.flatMap(modosDeGrupo);
    expect(todos).toHaveLength(new Set(todos).size);
  });

  it("un modo no está a la vez visible y plegado dentro del mismo grupo", () => {
    for (const grupo of GRUPOS_MODOS) {
      const solapan = grupo.modos.filter((m) => grupo.secundarios?.includes(m));
      expect(solapan, grupo.titulo).toEqual([]);
    }
  });

  it("toda capa definida es alcanzable desde el menú", () => {
    // El sentido contrario del test anterior: una capa en ESCALAS que no está en
    // ningún grupo existe en el código y se sirve por API, pero ningún usuario puede
    // llegar a ella. Se queda muerta sin que nada falle.
    const enMenu = new Set(GRUPOS_MODOS.flatMap(modosDeGrupo));
    const huerfanas = Object.keys(ESCALAS).filter((m) => !enMenu.has(m as Modo));
    expect(huerfanas).toEqual([]);
  });

  it("cada modo declara endpoint, campo y etiqueta", () => {
    for (const [modo, esc] of Object.entries(ESCALAS)) {
      expect(esc.endpoint, modo).toBeTruthy();
      expect(esc.campo, modo).toBeTruthy();
      expect(esc.etiqueta, modo).toBeTruthy();
    }
  });

  it("todo modo no categórico tiene buckets ordenados de mayor a menor", () => {
    for (const [modo, esc] of Object.entries(ESCALAS)) {
      if (esc.categorico) continue;
      expect(esc.buckets.length, modo).toBeGreaterThan(0);
      const umbrales = esc.buckets.map(([u]) => u);
      // `color` recorre los buckets en orden y devuelve el primero con v >= umbral.
      // Si no están ordenados descendentemente, devuelve el color equivocado.
      expect(umbrales, modo).toEqual([...umbrales].sort((a, b) => b - a));
    }
  });
});

describe("color", () => {
  const buckets: [number, string][] = [
    [70, "#alto"],
    [30, "#medio"],
    [0, "#bajo"],
  ];

  it("sin dato devuelve el gris neutro", () => {
    expect(color(buckets, null)).toBe("#e2e8f0");
  });

  it("elige el primer bucket cuyo umbral alcanza el valor", () => {
    expect(color(buckets, 100)).toBe("#alto");
    expect(color(buckets, 70)).toBe("#alto");
    expect(color(buckets, 69.9)).toBe("#medio");
    expect(color(buckets, 0)).toBe("#bajo");
  });

  it("por debajo del último umbral cae al color más bajo", () => {
    expect(color(buckets, -5)).toBe("#bajo");
  });
});

describe("combinaCustom", () => {
  // Espejo en cliente de indice.combina() del backend
  // (services/orchestrator/src/territorio_pipelines/indice.py). La duplicación es
  // consciente —permite mover los pesos sin ir al servidor— pero las dos
  // implementaciones deben coincidir, así que aquí se fija el contrato.
  const todos = {
    c_renta: 80,
    c_paro: 60,
    c_alquiler: 40,
    c_envejecimiento: 20,
    c_servicios: 100,
  };

  it("hace la media ponderada con los pesos por defecto", () => {
    // 0.25*80 + 0.20*60 + 0.20*40 + 0.15*20 + 0.20*100 = 20+12+8+3+20 = 63
    expect(combinaCustom(todos, PESOS_DEFECTO)).toBe(63);
  });

  it("renormaliza sobre los componentes presentes", () => {
    // Solo renta (0.25) y paro (0.20): (0.25*80 + 0.20*60) / 0.45 = 32/0.45 = 71.1
    expect(combinaCustom({ c_renta: 80, c_paro: 60 }, PESOS_DEFECTO)).toBe(71.1);
  });

  it("ignora null y undefined en vez de contarlos como cero", () => {
    const conHuecos = { c_renta: 80, c_paro: null, c_alquiler: undefined };
    // Contar el hueco como 0 daría un valor mucho menor; debe devolver solo renta.
    expect(combinaCustom(conHuecos, PESOS_DEFECTO)).toBe(80);
  });

  it("devuelve null si no hay ningún componente", () => {
    expect(combinaCustom({}, PESOS_DEFECTO)).toBeNull();
    expect(combinaCustom(null, PESOS_DEFECTO)).toBeNull();
  });

  it("con pesos a cero devuelve null en lugar de dividir por cero", () => {
    const ceros = Object.fromEntries(CLAVES_INDICE.map((k) => [k, 0]));
    expect(combinaCustom(todos, ceros as typeof PESOS_DEFECTO)).toBeNull();
  });
});

describe("PESOS_DEFECTO", () => {
  it("suma 1 y cubre todas las claves del índice", () => {
    const suma = CLAVES_INDICE.reduce((acc, k) => acc + PESOS_DEFECTO[k], 0);
    expect(suma).toBeCloseTo(1, 10);
    expect(Object.keys(PESOS_DEFECTO).sort()).toEqual([...CLAVES_INDICE].sort());
  });

  it("coincide con los PESOS del backend (indice.py)", () => {
    // Si cambias uno, cambia el otro: el mapa y el ranking usarían escalas distintas.
    expect(PESOS_DEFECTO).toEqual({
      renta: 0.25,
      paro: 0.2,
      alquiler: 0.2,
      envejecimiento: 0.15,
      servicios: 0.2,
    });
  });
});

describe("cobertura del catálogo", () => {
  it("los modos con serie temporal declaran su endpoint de años", () => {
    const conAnios: Modo[] = ["poblacion", "renta", "alquiler", "paro", "extranjeros"];
    for (const modo of conAnios) {
      expect(ESCALAS[modo].anios, modo).toBeTruthy();
    }
  });
});

describe("accesibilidad de las paletas divergentes", () => {
  // prediccion/futuro/futuro_cohorte comparten FUT_BUCKETS. La paleta original
  // (RdYlGn) fallaba el chequeo de daltonismo de la skill `dataviz`: verde y rojo son
  // los dos extremos del eje de confusión de la deuteranopia/protanopia, y aquí es
  // justo lo que hay que distinguir ("crece" vs "se vacía"). Ahora es azul/rojo.
  it("la capa de predicción no usa verde para 'crece'", () => {
    for (const modo of ["prediccion", "futuro", "futuro_cohorte"] as const) {
      const azulOrojo = /^#(08|31|6b|fc|d7|99)/i;
      for (const [, hex] of ESCALAS[modo].buckets) {
        expect(hex, `${modo} ${hex}`).toMatch(azulOrojo);
        expect(hex.toLowerCase(), `${modo} no debe volver a usar verde`).not.toMatch(
          /^#(00|1a|a6|31a3|78c6)/,
        );
      }
    }
  });
});
