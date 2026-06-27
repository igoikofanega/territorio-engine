"""fact_provincia_anual (tasas vitales provinciales del MNP)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fact_provincia_anual",
        sa.Column("cod_provincia", sa.String(length=2), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("tasa_natalidad", sa.Float()),
        sa.Column("tasa_mortalidad", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("fact_provincia_anual")
