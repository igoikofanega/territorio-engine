"""narrativa_municipio — informe narrativo precalculado con hash de datos.

Se regenera solo cuando cambian los datos de entrada (hash_datos). La API lo sirve tal
cual, sin generación en línea. Si el informe no pasa la validación de grounding, el campo
`texto` queda NULL y el frontend usa la plantilla determinista.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "narrativa_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("texto", sa.String()),
        sa.Column("hash_datos", sa.String(length=40), nullable=False),
        sa.Column("modelo", sa.String(length=80)),
        sa.Column("aceptado", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_table("narrativa_municipio")
