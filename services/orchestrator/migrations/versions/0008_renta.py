"""renta neta media por persona (columna en fact_municipio_anual)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-27
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fact_municipio_anual", sa.Column("renta_neta_media_persona", sa.Float()))


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "renta_neta_media_persona")
