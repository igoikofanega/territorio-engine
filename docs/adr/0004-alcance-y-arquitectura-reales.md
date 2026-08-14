# ADR 0004 — El alcance y la arquitectura reales

- **Estado:** aceptado
- **Fecha:** 2026-08-14
- **Sustituye parcialmente:** [0001](0001-mvp-scope-and-discipline.md) (alcance),
  [0003](0003-architecture-topology.md) (regla de vistas materializadas)

## Contexto

`AGENTS.md` establece que el alcance del MVP está congelado y que **"todo lo demás se
justifica en su propio ADR al entrar"**. Entre junio y agosto de 2026 el proyecto creció
bastante por encima de ese alcance sin registrar un solo ADR nuevo, y la documentación se
quedó describiendo un sistema que ya no es el que hay.

Este ADR no propone nada: **registra lo que ya pasó**, para que la documentación deje de
contradecir al código. Un revisor que lea `AGENTS.md` y luego el repositorio encuentra hoy
tres afirmaciones falsas, y eso es peor que no haber escrito la regla.

## Lo que dice la documentación y no es cierto

### 1. "MVP = 5 fuentes + MNP" (ADR 0001)

Hay **14 adaptadores de fuente**. Entraron sin ADR: SERPAVI (alquiler) —que el ADR 0001
listaba *explícitamente* como fuera de v1—, OpenStreetMap, Wikidata, Wikipedia, EEA
(calidad del aire), SETELECO (banda ancha) e INE 33571 (población extranjera).

### 2. "La API solo lee vistas materializadas" (ADR 0003 y `architecture.md`)

**No existe ninguna vista materializada en el repositorio.** La API hace JOIN en tiempo de
petición contra las tablas.

### 3. "Un solo modelo bandera: cohorte-componente" (ADR 0001)

El modelo bandera de facto es un `HistGradientBoostingRegressor`. El cohorte-componente
(Hamilton-Perry) existe, pero como una capa más. Además se añadieron LISA, clustering de
arquetipos, gemelos divergentes, puntos de inflexión, descomposición demográfica,
rendimiento out-of-sample y un clasificador de riesgo calibrado — buena parte del "menú de
cruces avanzados" que el ADR 0001 dejaba fuera de v1.

## Decisión

### Sobre el alcance: se acepta, y se cambia la regla

La ampliación **se acepta retroactivamente**. El proyecto encontró tracción y crecer fue lo
correcto; lo que falló fue el registro.

La regla de "un ADR por fuente" no se cumplió porque era desproporcionada: añadir una
fuente son ~150 líneas siguiendo un patrón ya establecido. Se sustituye por una **más
barata y por tanto más probable de cumplirse**:

> Toda fuente nueva se registra en la tabla de `NOTICE` con su licencia y en el README.
> Solo requiere ADR si cambia el **grano** (algo distinto de `municipio × año`), añade un
> **servicio**, o introduce una **dependencia pesada**.

El alcance vigente pasa a ser el que documenta el README, no el del ADR 0001.

### Sobre las vistas materializadas: se corrige la regla, no el código

Se elimina "la API solo lee vistas materializadas" como regla dura. Se mantiene la que de
verdad importaba y **sí se cumple**:

> Los JOIN espaciales y todo cálculo de geometría se precalculan offline. La API no ejecuta
> operaciones PostGIS de coste en tiempo de petición; solo `ST_AsGeoJSON` sobre geometría ya
> simplificada.

Ese era el riesgo real. Los JOIN por clave con índice sobre `(cod_municipio, anio)` no lo
son, y ninguna medición ha señalado ese punto como cuello de botella.

Las vistas materializadas quedan como **optimización documentada para cuando haga falta**:
el disparador es servir el coroplético nacional (8.131 municipios) en lugar de una
provincia. Ver `docs/architecture.md`.

### Sobre el modelo bandera

El modelo bandera es el de gradient boosting con backtest temporal. El cohorte-componente
se mantiene como proyección alternativa y como contraste metodológico: es un modelo
demográfico clásico y auditable frente a uno estadístico, y compararlos tiene valor.

### Sobre `matriz_municipio_anual`

Este asset se declaraba en la documentación como "el objetivo del MVP" mientras su
implementación era literalmente `log("STUB") ; return 0`. **Se elimina.**

La fusión que prometía **ya existe**, solo que distribuida: cada `load_*` de `loaders.py`
hace UPSERT de sus columnas sobre la clave `(cod_municipio, anio)`. La matriz se construye
por acumulación en vez de en un paso final. Un stub declarado como objetivo del proyecto es
peor que no tenerlo, porque lleva a creer que falta algo que en realidad está hecho.

`tests/test_smoke.py` comprueba ahora que ningún asset se limite a loguear y devolver 0.

## Deuda reconocida y no resuelta

Se deja constancia explícita, porque es la parte que más contradice los principios
declarados del proyecto:

- **Faltan las banderas de calidad de dato** (`flag_imputado_paro`, `flag_renta_secreto`,
  `flag_alteracion_municipal`) que especifica `matrix-spec.md`, pese a que "honestidad sobre
  los datos" es principio no negociable en `AGENTS.md`. Hoy no hay forma de distinguir un
  dato medido de uno enmascarado por secreto estadístico.
- **`dim_municipio` no es SCD2.** Sin linaje, las fusiones y segregaciones de municipios
  rompen la continuidad de las series sin avisar.
- **Las tasas vitales son provinciales.** La descomposición vegetativo/migratorio aplica
  tasas de provincia a poblaciones municipales: es una estimación, no una medición, y el
  error es mayor justo en los municipios pequeños, que son el objeto del proyecto.

Ninguna se resuelve aquí. Quedan como issues abiertos, no como omisiones.

## Consecuencias

- `AGENTS.md`, `architecture.md` y el ADR 0003 se actualizan para reflejar el sistema real.
- El ADR 0001 se mantiene como registro histórico de la decisión inicial, con una nota que
  apunta aquí. No se reescribe: un ADR superado es información, no un error.
