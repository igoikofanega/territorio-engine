"""inflexion_municipio (puntos de inflexión de la serie de población)

Revision ID: 0024
Revises: 0023
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inflexion_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio_inflexion", sa.Integer()),
        sa.Column("pend_antes", sa.Float()),  # hab/año antes del giro
        sa.Column("pend_despues", sa.Float()),  # hab/año después
        sa.Column("tipo", sa.String(length=16)),  # remonta | se hunde | acelera | frena | ...
        sa.Column("magnitud", sa.Float()),  # cambio de pendiente relativo (%/año)
    )


def downgrade() -> None:
    op.drop_table("inflexion_municipio")
