"""lisa_municipio (hot spots espaciales: Moran local por variable)

Revision ID: 0021
Revises: 0020
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lisa_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("variable", sa.String(length=20), primary_key=True),
        sa.Column("valor", sa.Float()),
        sa.Column("categoria", sa.String(length=10)),  # alto-alto | bajo-bajo | alto-bajo | bajo-alto | ns
        sa.Column("p", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("lisa_municipio")
