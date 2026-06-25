# ADR 0001 — Alcance del MVP y disciplina

- **Estado:** aceptado
- **Fecha:** 2026-06-25

## Contexto
El dominio invita a un alcance enorme (location intelligence, riesgo climático, alt-data,
12+ cruces de ML). El riesgo principal del proyecto es la dispersión: construir infra y
modelos antes de tener una matriz de datos viva.

## Decisión
1. **Pregunta-bandera única:** *¿hacia dónde va este pueblo (crece o se vacía)?*
2. **MVP = 5 fuentes con clave municipal limpia + MNP:** geometrías IGN, Padrón
   (población + pirámide), MNP (natalidad/mortalidad), Atlas de Renta ADRH, Paro SEPE,
   AEMET (clima). Ventana **2015→**.
3. **Un solo modelo bandera:** trayectoria poblacional por **cohorte-componente +
   suavizado espacial** de la migración neta.
4. **Disciplina de código mínimo (ponytail):** no añadir dependencias/abstracciones
   "por si acaso".

## Fuera de v1 (capas posteriores)
SAE bayesiano fino, Kriging Universal, NDVI/Copernicus, SERPAVI (alquiler), GDELT
(noticias), sección censal como grano operativo, y el menú de cruces avanzados
(gentrificación, nómadas digitales, isócronas sanitarias…).

## Consecuencias
El primer entregable con valor es la matriz `municipio × año` sobre esas fuentes y un
mapa que muestre la trayectoria. Todo lo demás se justifica en su propio ADR al entrar.
