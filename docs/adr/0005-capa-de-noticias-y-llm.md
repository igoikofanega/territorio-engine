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
