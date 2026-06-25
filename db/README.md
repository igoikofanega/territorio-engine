# db

PostgreSQL + PostGIS. La imagen `postgis/postgis` ejecuta los `.sql` de `init/` al
crear el volumen por primera vez (solo entonces).

El **esquema** (tablas `dim_municipio`, `fact_municipio_anual`, `fact_piramide`,
`municipio_vecinos`) se gestionará con **Alembic** y se añade junto al primer DDL.
Spec del modelo: [`../docs/matrix-spec.md`](../docs/matrix-spec.md).

SRID: 25830 (ETRS89 UTM30N, peninsular) para cálculos métricos; 4326 para el frontend.
Ojo Canarias (25828).
