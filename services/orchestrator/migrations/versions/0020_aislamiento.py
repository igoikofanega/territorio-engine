"""municipio_aislamiento (distancias a servicios y a la capital, en km)

Revision ID: 0020
Revises: 0019
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_aislamiento",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("km_salud", sa.Float()),  # al municipio con sanidad más cercano
        sa.Column("km_educacion", sa.Float()),
        sa.Column("km_capital", sa.Float()),  # a la capital de provincia (proxy: mayor población)
    )


def downgrade() -> None:
    op.drop_table("municipio_aislamiento")
