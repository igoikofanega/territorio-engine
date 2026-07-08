"""más meteo: temp máx/mín, extremo mínimo, días despejados, humedad

Revision ID: 0023
Revises: 0022
Create Date: 2026-07-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

_COLS = [
    "temp_max_media",  # media de las máximas (°C)
    "temp_min_media",  # media de las mínimas (°C)
    "temp_min_abs",  # mínima absoluta (°C, heladas)
    "dias_despejados",  # días despejados al año (proxy de sol)
    "humedad_media",  # humedad relativa media (%)
]


def upgrade() -> None:
    for c in _COLS:
        op.add_column("fact_municipio_anual", sa.Column(c, sa.Float()))


def downgrade() -> None:
    for c in _COLS:
        op.drop_column("fact_municipio_anual", c)
