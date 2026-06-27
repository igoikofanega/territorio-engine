"""proyeccion_municipio (proyección demográfica v1)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proyeccion_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio_base", sa.Integer()),
        sa.Column("pob_base", sa.Integer()),
        sa.Column("cagr", sa.Float()),
        sa.Column("anio_horizonte", sa.Integer()),
        sa.Column("pob_proyectada", sa.Integer()),
        sa.Column("cambio_pct", sa.Float()),
        sa.Column("trayectoria", sa.String()),
    )
    op.create_index("ix_proyeccion_trayectoria", "proyeccion_municipio", ["trayectoria"])


def downgrade() -> None:
    op.drop_table("proyeccion_municipio")
