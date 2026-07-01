"""clima: temperatura y precipitación (columnas en fact_municipio_anual)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fact_municipio_anual", sa.Column("temp_media_anual", sa.Float()))
    op.add_column("fact_municipio_anual", sa.Column("precip_anual_mm", sa.Float()))


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "precip_anual_mm")
    op.drop_column("fact_municipio_anual", "temp_media_anual")
