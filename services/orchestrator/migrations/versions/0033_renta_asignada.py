"""marca la renta que el INE asigna a los municipios de menos de 100 habitantes

Desde la edición ADRH 2020 el INE no deja en blanco la renta de los municipios de menos de
100 habitantes: les asigna la media de los municipios de ese tamaño de su provincia
(ediciones 2020 y 2021) o de su comarca agraria (desde 2022). Metodología ADRH, INE,
octubre 2025. Hasta 2019 esos municipios salían enmascarados (`flag_renta_secreto`).

Se guardaba como la renta propia del municipio. Es uno de cada seis municipios con renta
desde 2020 (1.290 en 2023), y justo los pequeños, que son los del problema que estudia el
proyecto.

Columna **calculada por la base** a partir de la propia fila: población y renta vienen de
fuentes distintas que se cargan en cualquier orden, y una marca escrita por un cargador
quedaría rancia en cuanto se recargara el otro. Con `COALESCE`, una fila sin población
vale `false` en vez de `NULL`.

Revision ID: 0033
Revises: 0032
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

_EXPRESION = (
    "COALESCE(renta_neta_media_persona IS NOT NULL AND anio >= 2020 "
    "AND poblacion_total < 100, false)"
)


def upgrade() -> None:
    op.add_column(
        "fact_municipio_anual",
        sa.Column("flag_renta_asignada", sa.Boolean(), sa.Computed(_EXPRESION, persisted=True)),
    )


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "flag_renta_asignada")
