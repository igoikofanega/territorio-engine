"""proyeccion_cohorte (proyección v2 Hamilton-Perry)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proyeccion_cohorte",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio_base", sa.Integer()),
        sa.Column("pob_base", sa.Integer()),
        sa.Column("anio_horizonte", sa.Integer()),
        sa.Column("pob_proyectada", sa.Integer()),
        sa.Column("cambio_pct", sa.Float()),
        sa.Column("trayectoria", sa.String()),
    )


def downgrade() -> None:
    op.drop_table("proyeccion_cohorte")
