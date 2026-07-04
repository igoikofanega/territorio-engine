"""demografia_municipio (descomposición vegetativo vs migratorio)

Revision ID: 0026
Revises: 0025
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demografia_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("saldo_vegetativo", sa.Integer()),  # nac−def estimado (tasas provinciales)
        sa.Column("saldo_migratorio", sa.Integer()),  # residuo
        sa.Column("cambio_total", sa.Integer()),
        sa.Column("dominante", sa.String(length=12)),  # vegetativo | migratorio
        sa.Column("tipo", sa.String(length=32)),
    )


def downgrade() -> None:
    op.drop_table("demografia_municipio")
