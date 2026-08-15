"""noticia_municipio (metadatos de prensa por municipio, GDELT DOC 2.0)

Grano `(municipio, artículo)`: el primero del repositorio que no es `municipio × año`.
Va en tabla propia, fuera de `fact_municipio_anual`, para que la matriz principal siga
siendo lo que dice ser. Ver docs/adr/0005-capa-de-noticias-y-llm.md.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "noticia_municipio",
        sa.Column("cod_municipio", sa.String(length=5), primary_key=True),
        # La URL no puede ser clave: hay enlaces de más de 2.700 bytes y no caben en un
        # índice B-tree de PostgreSQL. El sha1 es identificador, no medida de seguridad.
        sa.Column("url_sha1", sa.String(length=40), primary_key=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("titular", sa.String(), nullable=False),  # nunca el cuerpo (ADR 0005)
        sa.Column("medio", sa.String(length=160)),
        sa.Column("fecha", sa.Date(), index=True),
        sa.Column("idioma", sa.String(length=20)),
        # Salida de la extracción con LLM: nulas hasta que se ejecuta.
        sa.Column("pertenece", sa.Boolean()),  # ¿habla de ESTE municipio? (caso Tudela)
        sa.Column("confianza", sa.Float()),
        sa.Column("tema", sa.String(length=40)),
        sa.Column("signo", sa.Float()),
        sa.Column("modelo", sa.String(length=80)),
    )


def downgrade() -> None:
    op.drop_table("noticia_municipio")
