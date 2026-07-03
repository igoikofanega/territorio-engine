"""extensión unaccent + wrapper inmutable f_unaccent para búsquedas

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-02
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    # wrapper inmutable → utilizable en expresiones parametrizadas / índices
    op.execute(
        "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text "
        "AS $$ SELECT public.unaccent('public.unaccent', $1) $$ "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_dim_municipio_nombre_norm "
        "ON dim_municipio (f_unaccent(lower(nombre)))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_dim_municipio_nombre_norm")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
    # dejamos la extensión instalada
