"""municipio_aire (calidad del aire: PM2.5, NO2, PM10, O3 — EEA interpolado)

Revision ID: 0028
Revises: 0027
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "municipio_aire",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        sa.Column("pm25", sa.Float()),  # media anual PM2.5 (µg/m³)
        sa.Column("no2", sa.Float()),  # media anual NO2 (µg/m³)
        sa.Column("pm10", sa.Float()),  # media anual PM10 (µg/m³)
        sa.Column("o3", sa.Float()),  # indicador de pico de O3
    )


def downgrade() -> None:
    op.drop_table("municipio_aire")
