-- Se ejecuta una sola vez al crear el volumen de la base de datos.
CREATE EXTENSION IF NOT EXISTS postgis;
-- Útil para búsquedas por nombre de municipio (acentos/typos) más adelante:
CREATE EXTENSION IF NOT EXISTS pg_trgm;
