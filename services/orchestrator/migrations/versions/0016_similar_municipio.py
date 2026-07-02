"""similar_municipio ('pueblos como el tuyo')

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "similar_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("similares", sa.String()),  # códigos vecinos separados por coma
    )


def downgrade() -> None:
    op.drop_table("similar_municipio")
