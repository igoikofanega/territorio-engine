"""arquetipo_municipio (clustering de municipios)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "arquetipo_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("cluster", sa.Integer()),
        sa.Column("etiqueta", sa.String()),
    )


def downgrade() -> None:
    op.drop_table("arquetipo_municipio")
