"""indice_municipio (índice compuesto "¿dónde vivir?")

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "indice_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("score", sa.Float()),
        sa.Column("c_renta", sa.Float()),
        sa.Column("c_paro", sa.Float()),
        sa.Column("c_alquiler", sa.Float()),
        sa.Column("c_envejecimiento", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("indice_municipio")
