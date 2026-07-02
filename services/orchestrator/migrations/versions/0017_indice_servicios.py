"""c_servicios en indice_municipio (componente servicios OSM)

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("indice_municipio", sa.Column("c_servicios", sa.Float()))


def downgrade() -> None:
    op.drop_column("indice_municipio", "c_servicios")
