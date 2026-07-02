"""municipio_servicios (equipamientos OSM por municipio)

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_servicios",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("n_salud", sa.Integer()),
        sa.Column("n_educacion", sa.Integer()),
        sa.Column("n_comercio", sa.Integer()),
        sa.Column("n_total", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("municipio_servicios")
