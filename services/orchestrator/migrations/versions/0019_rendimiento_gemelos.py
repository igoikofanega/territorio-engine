"""rendimiento_municipio (residuos out-of-sample) + gemelo_municipio (gemelos divergentes)

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rendimiento_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("residuo", sa.Float()),  # puntos porcentuales sobre lo predicho
        sa.Column("z", sa.Float()),
        sa.Column("n_obs", sa.Integer()),
        sa.Column("clasificacion", sa.String(length=10)),  # sobre | esperado | bajo
    )
    op.create_table(
        "gemelo_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("cod_gemelo", sa.String(length=5)),
        sa.Column("distancia", sa.Float()),  # distancia en el espacio de features
        sa.Column("crec_propio", sa.Float()),
        sa.Column("crec_gemelo", sa.Float()),
        sa.Column("divergencia", sa.Float()),
    )


def downgrade() -> None:
    op.drop_table("gemelo_municipio")
    op.drop_table("rendimiento_municipio")
