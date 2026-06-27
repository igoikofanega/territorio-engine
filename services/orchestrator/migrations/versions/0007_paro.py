"""paro registrado (columna en fact_municipio_anual)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fact_municipio_anual", sa.Column("paro_media_anual", sa.Integer()))


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "paro_media_anual")
