"""alquiler €/m² (columna en fact_municipio_anual)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fact_municipio_anual", sa.Column("alquiler_eur_m2", sa.Float()))


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "alquiler_eur_m2")
