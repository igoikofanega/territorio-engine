"""banderas de calidad de dato en fact_municipio_anual

`AGENTS.md` declara la honestidad sobre los datos como principio no negociable —"marca con
flags lo imputado/enmascarado/estimado"— y hasta ahora un NULL podía significar tres cosas
distintas sin forma de distinguirlas. Estas dos columnas separan lo que se sabe de lo que
no.

`flag_renta_secreto`: el INE publica la fila del municipio-año con el valor VACÍO cuando
la renta está protegida por secreto estadístico. El adaptador descartaba esas filas, así
que el hueco quedaba indistinguible de "no recogido". No es un detalle contable: la
ausencia está correlacionada con el tamaño (en 2016, el 33% de los municipios de menos de
500 habitantes frente al 0% de los de 500-1.000), y el tamaño predice el target. El modelo
veía un NaN neutro donde había información.

`paro_meses`: la media anual del paro se calcula sobre los meses que haya en el CSV del
SEPE. Un año con 3 meses cargados y otro con 12 daban una columna idéntica. El conteo
permite distinguirlos y descartar los años a medias.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fact_municipio_anual",
        sa.Column("flag_renta_secreto", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "fact_municipio_anual",
        sa.Column("paro_meses", sa.SmallInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fact_municipio_anual", "paro_meses")
    op.drop_column("fact_municipio_anual", "flag_renta_secreto")
