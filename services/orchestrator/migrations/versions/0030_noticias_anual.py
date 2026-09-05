"""municipio_noticias_anual — noticias agregadas a (municipio, año)

Agrega los metadatos de prensa etiquetados (noticia_municipio WHERE pertenece = true) al
grano `municipio × año` del resto del repositorio. Las columnas son conteos y tasas que
sirven tanto a la API (panel de noticias) como a las features del modelo.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_noticias_anual",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("n_noticias", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_positivas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_negativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_empleo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_empresa", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_vivienda", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_servicios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("n_infraestructura", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("municipio_noticias_anual")
