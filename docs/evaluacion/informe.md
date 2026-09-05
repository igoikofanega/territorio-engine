# Informe de evaluación

> **Generado por `make evaluar`.** No editar a mano: se regenera desde la base de datos.
> Las cifras de este fichero son las que debe citar el README.

Horizonte de predicción: **5 años**. Target: variación porcentual de
población entre el año base T y T+5.

## 1. Backtest de origen rodante

Un pliegue por año base de validación, entrenando siempre solo con años anteriores.
Un corte único da una cifra sin dispersión que parece más precisa de lo que es.

| Año de validación | Entrena con | n val | MAE | R² | MAE persistencia | MAE tendencia |
|---|---|---|---|---|---|---|
| 2019 | 2015-2018 | 8.131 | 5,633 | 0,404 | 7,662 | 10,192 |
| 2020 | 2015-2019 | 8.131 | 5,960 | 0,302 | 7,632 | 9,844 |

**MAE = 5,796 ± 0,231 pp** (2 pliegues,
rango 5,633–5,960).

Pliegues descartados y por qué:

- 2016: sin dato en entrenamiento para crec_prev3
- 2017: sin dato en entrenamiento para crec_prev3
- 2018: sin dato en entrenamiento para crec_prev3

### El coste del solape

El target mira 5 años adelante, así que con pliegues contiguos las ventanas
de train y validación comparten trayectoria sobre los mismos municipios. Separarlas exige
un embargo, y la ventana de datos disponible no da para mucho:

| Embargo (años) | Pliegues | MAE medio | Nota |
|---|---|---|---|
| 2 | 1 | 6,329 |  |
| 3 | 0 | — | sin pliegues con datos suficientes |
| 4 | 0 | — | sin pliegues con datos suficientes |
| 5 | 0 | — | sin pliegues con datos suficientes |

Con embargo 1 el MAE es 5,796; con embargo 2, 6,329. La diferencia
es el precio de haber estado midiendo sobre ventanas solapadas. **Un embargo completo
(= el horizonte) no es factible hoy**: la población empieza en 2015 y no quedan años base
suficientes. Es una limitación de los datos, no una decisión de diseño, y se declara en
vez de publicar el número más favorable.

## 2. Dónde falla el modelo

![Error por estrato de población](./error-por-estrato.png)

| Tamaño | n | MAE | Sesgo | MAE si no cambia nada |
|---|---|---|---|---|
| <500 | 4.001 | 8,53 | -0,49 | 9,83 |
| 500-2000 | 1.871 | 4,24 | +1,21 | 5,88 |
| 2000-10000 | 1.500 | 3,07 | +0,48 | 5,47 |
| >10000 | 759 | 2,36 | +0,11 | 4,63 |

Esto es lo que un MAE agregado esconde: el error en los municipios de menos de 500
habitantes es **3,6 veces**
el de los de más de 10.000. Y son justo los municipios por los que existe este proyecto.
La comparación honesta no es contra cero, sino contra "no cambia nada" en cada estrato:
ahí el modelo sigue ganando, pero por menos de lo que sugiere la cifra global.

### Las cinco provincias donde peor va

| Provincia | n | MAE | Sesgo |
|---|---|---|---|
| 19 | 288 | 15,02 | -2,60 |
| 42 | 183 | 11,40 | -5,28 |
| 16 | 238 | 9,77 | +1,74 |
| 26 | 174 | 9,61 | -0,65 |
| 40 | 209 | 9,56 | +2,85 |

## 3. ¿Le sobra estructura espacial al residuo?

Moran's I sobre el error del pliegue más reciente, con 8 vecinos más
próximos por centroide:

- **I = 0,1137** (esperado bajo azar: -0,0001), p = 0,001, n = 8.131

El error **no** está repartido al azar en el mapa: municipios vecinos fallan en el mismo
sentido. Queda geografía que las 17 features no capturan. Es un
resultado esperable —la despoblación es un fenómeno regional, no municipal— y marca la
dirección de mejora más clara: una feature de contexto comarcal, o un término espacial
explícito.

## 4. Qué mueve la predicción

![Importancia por permutación](./importancia.png)

Importancia por permutación sobre el pliegue más reciente. Mide **asociación, no causa**:
que `crec_prev3` pese mucho no significa que la tendencia cause el futuro, sino que
resume información que las demás variables no traen.

## 5. Calibración del semáforo de despoblación

Evento: perder más del 10 % de la población en 5 años.
Partición de tres tramos, todos temporales: se entrena con 2015-2018,
se calibra con 2019 y se mide con **2020**, que el calibrador
no ha visto.

| | |
|---|---|
| AUC | 0,8423 |
| Brier sin calibrar | 0,07559 |
| Brier calibrado (isotónica) | 0,07675 |
| Tasa base del evento | 0,0980 |
| n | 8.131 |

![Diagrama de fiabilidad](./fiabilidad.png)

| Tramo | n | Promete | Ocurre |
|---|---|---|---|
| 0.0-0.1 | 5.415 | 0,020 | 0,027 |
| 0.1-0.2 | 1.374 | 0,137 | 0,176 |
| 0.2-0.3 | 803 | 0,269 | 0,273 |
| 0.3-0.4 | 25 | 0,333 | 0,320 |
| 0.4-0.5 | 339 | 0,428 | 0,298 |
| 0.5-0.6 | 20 | 0,545 | 0,200 |
| 0.6-0.7 | 142 | 0,614 | 0,493 |
| 0.7-0.8 | 10 | 0,775 | 0,500 |
| 0.8-0.9 | 3 | 0,800 | 0,333 |

**Resultado negativo, y se publica igual.** Medida fuera de la muestra en que se ajusta,
la calibración isotónica **no mejora** el Brier (0,07675 frente a
0,07559 sin calibrar). El diagrama enseña por qué: por encima del
40 % el modelo promete más de lo que ocurre, y los tramos altos tienen tan pocos
municipios que la isotónica no tiene con qué corregirlos.

La consecuencia práctica es que **el semáforo ordena bien pero no cuantifica bien**: el
AUC de 0,84 dice que separa los municipios en riesgo de los que no, y eso es lo
que usa la interfaz (verde / ámbar / rojo). Lo que no se sostiene es leer la probabilidad
como una frecuencia literal.
