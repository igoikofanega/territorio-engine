# ADR 0005 — Capa de noticias y LLM

- **Estado:** aceptado
- **Fecha:** 2026-08-15

## Por qué este ADR sí hace falta

La regla vigente ([ADR 0004](0004-alcance-y-arquitectura-reales.md)) dice que una fuente
nueva solo necesita ADR si **cambia el grano**, **añade un servicio** o **mete una
dependencia pesada**. Esta cambia el grano —una noticia no es `municipio × año`— y añade
una dependencia (`openai`) más un proveedor externo de pago. Además introduce una
pregunta que el resto del repositorio no se había hecho nunca: qué contenido de terceros
podemos almacenar y servir.

## Contexto

La pregunta que se quiere responder es si lo que se **cuenta** de un municipio anticipa lo
que le **pasa**: si el flujo de noticias locales contiene señal sobre el vaciamiento que
las series estadísticas todavía no muestran.

Antes de escribir código se comprobaron empíricamente las dos fuentes candidatas, y ambas
resultaron más limitadas de lo que prometían:

| Fuente | Hallazgo |
|---|---|
| Google News RSS | Funciona (100 artículos, 30 medios) pero solo guarda **~4 meses** de histórico. Inútil para features de ML. |
| GDELT DOC 2.0 | Tiene histórico, pero **arranca en 2017** y limita a **1 petición cada 5 segundos** (devuelve un aviso en texto plano, no JSON, si se abusa). |

Se sondeó también la cobertura real. La consulta de "Tudela" en 2019 devuelve 250
artículos —el tope de `maxrecords`, o sea que satura—, pero entre los primeros resultados
aparece `elnortedecastilla.es` hablando de **Tudela de Duero (Valladolid)**. La
homonimia municipal española no es un caso raro: es el problema central de esta capa.

## Decisiones

### 1. Fuente: GDELT DOC 2.0. Ámbito: Navarra

GDELT es la única fuente verificada con histórico suficiente. El ámbito es **Navarra (272
municipios)**, coherente con el ámbito por defecto del frontend, y el diseño no asume
Navarra en ninguna parte: la ingesta recibe una lista de códigos de municipio.

Esto crea una capa **regional** en un proyecto **nacional**. Se acepta, con la condición
de que la interfaz la marque como tal: un municipio de Cuenca sin noticias no es un
municipio sin noticias, es un municipio no consultado. Confundir "no hay dato" con "el
dato es cero" es exactamente lo que el principio de honestidad sobre los datos prohíbe.

### 2. Grano: `(cod_municipio, artículo)`, no `municipio × año`

La tabla nueva `noticia_municipio` tiene una fila por artículo atribuido a un municipio.
No entra en `fact_municipio_anual`. La agregación a `municipio × año` se hace en la capa
de features, que es donde se decide la ventana, no en la ingesta.

Es el primer grano no anual del repositorio. Se aísla a propósito en su propia tabla para
que la matriz principal siga siendo lo que dice ser.

### 3. Qué se almacena y qué no

> Se almacenan **titular, fecha, medio (dominio), URL, idioma y etiquetas derivadas**.
> **Nunca el cuerpo del artículo.**

El titular es una cita breve e identificativa; el cuerpo es la obra. No se descarga, no se
guarda y no se envía al proveedor de LLM. La API sirve el titular con su enlace al medio
original, que es tráfico hacia el medio, no sustitución del medio.

Los titulares pueden contener nombres de personas. No se construye ningún índice por
persona ni se hace ningún tratamiento cuyo objeto sea una persona: la unidad de análisis
es el municipio. Si en el futuro alguien quiere lo contrario, que sea otro ADR.

GDELT se añade a `NOTICE` con su licencia junto a las otras 14 fuentes.

### 4. Proveedor de LLM: SDK `openai` contra `base_url` configurable

Se usa el SDK `openai` de Python apuntando a un `base_url` que sale de la configuración.
**No** el SDK de Anthropic, y no porque el modelo importe poco, sino porque el protocolo
de OpenAI se ha convertido en el denominador común: el mismo código sirve para OpenAI,
Groq, DeepSeek, OpenRouter, vLLM o un Ollama local si algún día lo hay.

Configuración por entorno, con `.env.example` documentado y sin valores por defecto que
gasten dinero: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODELO`.

Es una dependencia ligera (se apoya en `httpx` y `pydantic`, ya presentes) y **no añade un
servicio**: el cliente vive dentro del orchestrator, que es el único que escribe.

> **Los tests siguen pasando sin red y sin clave.** Toda llamada al proveedor va con
> respuestas grabadas. Un repositorio que solo se puede validar teniendo una clave de pago
> no es reproducible para quien lo clone.

### 5. La desambiguación es la tarea, no un preproceso

El trabajo principal del LLM **no** es el análisis de sentimiento: es decidir si un titular
habla del municipio por el que se preguntó. El caso Tudela / Tudela de Duero se
manifestará en decenas de municipios navarros (Cascante, Ablitas, Buñuel, Mendavia…
comparten nombre o raíz con topónimos de otras provincias).

Por eso la extracción devuelve, por titular: **pertenencia** al municipio consultado
(con confianza), **tema** y **signo**. Y por eso el golden set se construye **antes** que
las features: medir la calidad de esa decisión es requisito previo a usarla.

### 6. Puerta de decisión, con el número escrito antes de mirarlo

Tras el piloto de ingesta se mide `n_municipios_con_cobertura` = municipios navarros con
al menos un artículo atribuido tras desambiguación.

> **Si salen menos de 60, se cancela la parte de ML.** La capa se queda como producto
> (panel de noticias en la ficha) y no se construyen features.

Con menos de 60 municipios de 272, cualquier métrica de ablación sería ruido con formato
de tabla.

### 7. La ablación tiene configuración propia y su MAE no es comparable

Los años base del modelo de producción son 2015-2020. Con GDELT desde 2017 y una ventana
`[T-2, T]`, solo 2019 y 2020 tendrían cobertura completa — **y son justo los años de
validación**. Comparar en esas condiciones mediría el hueco de datos, no las noticias.

La ablación usa por tanto **años base 2018-2021, horizonte 3 años y solo municipios
navarros**.

> **El MAE de la ablación no es comparable con el 5,79 pp del modelo bandera.** Distinto
> horizonte, distinto ámbito y distinta ventana. Cualquier sitio donde se publique este
> número debe decirlo en la misma pantalla.

### 8. Criterio de aceptación, fijado aquí y ahora

Esto se escribe **antes** de haber visto ningún resultado, y no se toca después. Es la
parte de este ADR que de verdad importa: un criterio decidido después de ver el número no
es un criterio.

Tres brazos, misma partición temporal, mismos hiperparámetros, semillas `random_state`
0-4:

| Brazo | Features |
|---|---|
| **A · sin** | las 17 actuales |
| **B · con** | las 17 + las de noticias |
| **C · permutadas** | las 17 + las de noticias **barajadas entre municipios dentro del mismo año base** |

El brazo C es lo que hace creíble el resultado. Conserva la distribución marginal de las
features de noticias y destruye solo su vínculo con el municipio: si B mejora sobre A pero
C mejora igual, lo que se ha medido es la capacidad del modelo de aprovechar ruido extra,
no información.

**Se declara que las noticias aportan señal si y solo si se cumplen las tres condiciones:**

1. **Δ_real** = MAE(A) − MAE(B) ≥ **0,20 pp** (mejora mínima de interés).
2. **Δ_placebo** = MAE(A) − MAE(C) < Δ_real / 2.
3. El **IC del 95 % por bootstrap** (1.000 remuestreos de los municipios de validación) de
   la diferencia por municipio |error_A| − |error_B| **excluye el 0**.

Si no se cumplen las tres, las features **no entran en el modelo de producción** y el
resultado se publica igualmente como negativo, con sus números.

## Predicción registrada

Se deja constancia, para que no se pueda reescribir a posteriori: **lo más probable es que
las noticias no mejoren el MAE.** Tres razones estructurales:

1. Buena parte de los municipios navarros probablemente no aparezcan en GDELT ni una vez
   (la mayoría tienen menos de 500 habitantes).
2. La desalineación temporal descrita arriba.
3. **Redundancia.** "Cierra la fábrica" llega el mismo año que sube el paro, y
   `paro_1000` ya lo captura antes, mejor medido y para los 8.131 municipios.

El valor de esta fase no está en que salga que sí. Está en medirlo de forma que el "no"
también sea publicable.

## Consecuencias

- Tabla nueva `noticia_municipio` (migración 0029), fuera de `fact_municipio_anual`.
- Dependencia nueva `openai` en el orchestrator; tres variables de entorno nuevas.
- GDELT entra en `NOTICE` y en el README.
- La ingesta completa (272 × 2017-2025 ≈ 2.448 peticiones a 5,5 s) son casi 4 horas: la
  ingesta aterriza el crudo en `/data/raw/gdelt/` y es **reanudable**. Se empieza por un
  piloto para no comprometer 4 horas antes de saber si la puerta pasa.
- El frontend marca la capa como **regional (Navarra)**, no como ausencia de dato.

## Nota de auditoría — 2026-09-05

**El criterio de la sección 8 no se toca.** Esta nota existe porque durante un tiempo el
código *no lo aplicó*, y eso debe quedar registrado en vez de corregirse en silencio.

La primera implementación de `ml/ablacion.py` decidía con otro criterio —`mae(con) <
mae(sin) − 2·sd(semillas)` y `mae(con) < mae(permutadas)`, sobre un estrato de población—
sin el umbral absoluto de 0,20 pp y **sin el intervalo bootstrap**, con años base
derivados de los datos en vez de 2018-2021, sin filtrar por provincia y permutando la
columna entera en vez de dentro de cada año base. Su docstring presentaba ese criterio
como si fuera el preinscrito.

Se ha reescrito para aplicar literalmente las tres condiciones de la sección 8, la
configuración de la sección 7 y la puerta de cobertura de la sección 6, que tampoco
estaba implementada. Lo protege `tests/test_ablacion.py`, que falla si alguien cambia los
umbrales.

La corrección se hace **con el etiquetado al 38 % y sin haber ejecutado la ablación
todavía**: no se ha visto ningún resultado al decidirla. Ese es justamente el punto — un
criterio ajustado después de ver el número no es un criterio, y un criterio que el código
no aplica tampoco lo es.

## Golden set — quién lo etiquetó y qué salió (2026-09-06)

**Advertencia que hay que leer antes que el número: la referencia la etiquetó un modelo,
no una persona.** Concretamente Claude Opus 5, con el criterio escrito en el propio
fichero de generación. Es una referencia *cuidadosa* frente a un *clasificador barato*
(Gemini 3.1 Flash Lite), no una verdad humana. Todo lo que sigue hereda ese límite: mide
acuerdo entre dos modelos, y un sesgo compartido por ambos sería invisible aquí.

La muestra pasó de 1.303 filas a **193**. La estratificación se pensó con ~20 municipios
cubiertos (8 × 20 ≈ 160); con 189 cubiertos se disparó a un tamaño que nadie puede
etiquetar con cuidado. El recorte sortea **municipios enteros**, no filas: recortar filas
habría dejado la muestra dominada por los municipios con más prensa, que son los grandes,
justo el sesgo que la estratificación existe para evitar.

Criterio de anotación, uniforme: `pertenece` es verdadero solo si el titular habla del
municipio concreto o de una entidad que lo contiene de forma estrecha y nombrada (su
comarca, su mancomunidad, un concejo suyo). **Una noticia de alcance navarro que no lo
menciona no pertenece**: si perteneciera, la feature de prensa mediría cobertura regional,
no local.

### Resultado

| | |
|---|---|
| Titulares comparados | 162 (de 193; 31 aún sin etiquetar por el modelo) |
| Acierto en `pertenece` | **0,951** |
| Precisión / recall | 0,84 / 0,84 |
| Matriz de confusión | VP 21 · FP 4 · FN 4 · VN 133 |
| Decir "sí" a todo acertaría | 0,154 |
| Acierto de `tema` | 0,92 |

**El eslabón se sostiene.** El clasificador barato hace bien la desambiguación, que era la
duda: con una tasa base del 15 %, un 95 % de acierto no se consigue asintiendo.

### El dato que cambia cómo hay que leer la capa

Solo el **13,5 %** de los titulares que GDELT atribuye a un municipio hablan de verdad de
él. La homonimia no es un detalle: en Garde, Jaurrieta, Larraga, Legarda, Leitza, Luquin,
Peralta, Sangüesa y Tirapu, **ninguno** de los ocho titulares muestreados era del
municipio. "Garde" cuela como palabra suelta, "Peralta" y "Legarda" como apellidos,
"Jaurrieta" arrastra ruido de cartelera de cine.

Consecuencia para la ablación: el filtrado del LLM no es un preproceso opcional, es la
mitad del trabajo. Y para los municipios pequeños, después de filtrar puede no quedar
casi nada — que es exactamente lo que anticipaba la predicción registrada más arriba.

## Veredicto de la ablación — 2026-09-06

Ejecutada con el etiquetado completo (34.126 titulares) y 160 municipios con cobertura,
por encima del mínimo de 60 de la sección 6. El criterio aplicado es el de la sección 8,
sin tocar.

> **Este MAE no es comparable con el 5,74 pp del modelo bandera.** Horizonte 3 en vez de
> 5, solo Navarra en vez de España, y otra ventana de años. Sección 7.

| Brazo | MAE (pp) |
|---|---|
| **A · sin** noticias | 4,097 |
| **B · con** noticias | 4,068 |
| **C · permutadas** (placebo) | 4,157 |

| Condición | Umbral | Medido | ¿Se cumple? |
|---|---|---|---|
| 1 · Δ_real ≥ 0,20 pp | 0,20 | **0,029** | ❌ |
| 2 · Δ_placebo < Δ_real/2 | 0,015 | −0,060 | ✅ |
| 3 · IC 95 % excluye el 0 | — | **[−0,040 · 0,099]** | ❌ |

**Decisión: rechazar.** Las features de prensa **no entran** en el modelo de producción.

La condición 2 se cumple, pero sola no dice nada: que el placebo salga *peor* que la base
(−0,060) significa que añadir cuatro columnas de ruido empeora el ajuste, que es lo
esperable. Lo que decide es que la mejora real, 0,029 pp, es siete veces menor que el
umbral mínimo de interés, y que su intervalo de confianza contiene el cero con holgura.

La ablación descartó `alquiler` del conjunto base: SERPAVI no cubre el ámbito en 2018-2019
y una columna entera a NaN degenera el modelo. Se aplica igual a los tres brazos, así que
la diferencia entre ellos sigue siendo solo la prensa.

### Lo que esto confirma

La **predicción registrada** más arriba —escrita antes de ver ningún dato— decía que lo
más probable era que las noticias no mejorasen el MAE, por tres razones estructurales. Las
tres se sostienen, y el golden set añadió la cuarta y más contundente: **solo el 13,5 % de
los titulares que GDELT atribuye a un municipio hablan de él**. Después de filtrar la
homonimia, a los pueblos pequeños —que son el objeto del proyecto— no les queda casi nada.

El desglose por estrato lo enseña: la mejora es mayor en los municipios de 2.000-10.000
habitantes (1,994 → 1,923) que en los de menos de 500 (5,574 → 5,551), justo al revés de
lo que haría falta.

### Qué se queda y qué no

- **La capa se queda como producto**: el panel de prensa en la ficha, marcado como capa
  regional. Es útil para leer un municipio aunque no prediga su población.
- **Las features no entran en `FEATURES`.** Siguen existiendo en `features_noticias.py`,
  consumidas solo por la ablación, que es quien tenía que decidir.
- El valor de esta fase no estaba en que saliera que sí, sino en medirlo de forma que el
  "no" también fuese publicable. Está publicado.
