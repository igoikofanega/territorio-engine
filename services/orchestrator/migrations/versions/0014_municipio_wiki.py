"""municipio_wiki (hechos Wikidata + descripción Wikipedia)

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_wiki",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("altitud", sa.Float()),
        sa.Column("web", sa.String()),
        sa.Column("imagen", sa.String()),
        sa.Column("escudo", sa.String()),
        sa.Column("gentilicio", sa.String()),
        sa.Column("wiki_titulo", sa.String()),
        sa.Column("descripcion", sa.Text()),  # se rellena con el adaptador de Wikipedia
        sa.Column("wiki_imagen", sa.String()),
    )


def downgrade() -> None:
    op.drop_table("municipio_wiki")
