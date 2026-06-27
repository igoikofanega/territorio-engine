"""fact_piramide (pirámide de edad municipal)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fact_piramide",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("sexo", sa.String(length=1), primary_key=True),
        sa.Column("edad_min", sa.Integer(), primary_key=True),
        sa.Column("poblacion", sa.Integer()),
    )
    op.create_index("ix_fact_piramide_cod_anio", "fact_piramide", ["cod_municipio", "anio"])


def downgrade() -> None:
    op.drop_table("fact_piramide")
