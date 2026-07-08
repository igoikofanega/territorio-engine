"""municipio_conectividad (cobertura de banda ancha: fibra, 100Mbps, 5G)

Revision ID: 0027
Revises: 0026
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_conectividad",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("pct_fibra", sa.Float()),  # % hogares con FTTH (junio 2025)
        sa.Column("pct_100mbps", sa.Float()),  # % hogares con cobertura >=100 Mbps
        sa.Column("pct_5g", sa.Float()),  # % hogares con 5G
    )


def downgrade() -> None:
    op.drop_table("municipio_conectividad")
