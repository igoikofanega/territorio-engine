"""dim_municipio (tabla maestra + geometrías)

Revision ID: 0001
Revises:
Create Date: 2026-06-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "dim_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("cod_provincia", sa.String(length=2), nullable=False),
        sa.Column("cod_ccaa", sa.String(length=2)),
        sa.Column("superficie_km2", sa.Float()),
    )
    op.execute("SELECT AddGeometryColumn('dim_municipio', 'geom_4326', 4326, 'MULTIPOLYGON', 2)")
    op.execute("SELECT AddGeometryColumn('dim_municipio', 'geom_25830', 25830, 'MULTIPOLYGON', 2)")
    op.create_index("ix_dim_municipio_cod_provincia", "dim_municipio", ["cod_provincia"])
    op.execute("CREATE INDEX ix_dim_municipio_geom_4326 ON dim_municipio USING GIST (geom_4326)")


def downgrade() -> None:
    op.drop_table("dim_municipio")
