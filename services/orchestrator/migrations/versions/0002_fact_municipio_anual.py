"""fact_municipio_anual (población del Padrón)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fact_municipio_anual",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("poblacion_total", sa.Integer()),
        sa.Column("poblacion_hombres", sa.Integer()),
        sa.Column("poblacion_mujeres", sa.Integer()),
    )
    op.create_index("ix_fact_municipio_anual_anio", "fact_municipio_anual", ["anio"])


def downgrade() -> None:
    op.drop_table("fact_municipio_anual")
