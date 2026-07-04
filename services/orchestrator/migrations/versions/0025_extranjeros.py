"""población extranjera y % de extranjeros por municipio·año

Revision ID: 0025
Revises: 0024
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fact_municipio_anual", sa.Column("poblacion_extranjera", sa.Integer()))
    op.add_column("fact_municipio_anual", sa.Column("pct_extranjeros", sa.Float()))


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "pct_extranjeros")
    op.drop_column("fact_municipio_anual", "poblacion_extranjera")
