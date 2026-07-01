"""prediccion_ml (predicción del modelo ML)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prediccion_ml",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio_base", sa.Integer()),
        sa.Column("anio_horizonte", sa.Integer()),
        sa.Column("pob_base", sa.Integer()),
        sa.Column("pob_proyectada", sa.Integer()),
        sa.Column("cambio_pct", sa.Float()),
        sa.Column("cambio_inf", sa.Float()),
        sa.Column("cambio_sup", sa.Float()),
        sa.Column("drivers", sa.String()),
    )


def downgrade() -> None:
    op.drop_table("prediccion_ml")
