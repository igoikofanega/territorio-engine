"""riesgo_municipio (semáforo de despoblación: probabilidad calibrada)

Revision ID: 0022
Revises: 0021
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "riesgo_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("prob", sa.Float()),  # P(pérdida fuerte de población a 5 años)
        sa.Column("nivel", sa.String(length=6)),  # verde | ambar | rojo
    )


def downgrade() -> None:
    op.drop_table("riesgo_municipio")
