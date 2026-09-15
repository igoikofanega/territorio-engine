from dagster import AssetSelection, Definitions, define_asset_job, load_assets_from_modules

from territorio_pipelines import assets
from territorio_pipelines.comprobaciones import COMPROBACIONES
from territorio_pipelines.schedules import SCHEDULES

# Las comprobaciones corren solas tras materializar su asset. Este job las lanza todas
# sueltas, sin recargar nada, para poder auditar la matriz tal como está (`make comprobar`).
job_comprobaciones = define_asset_job(
    name="comprobaciones",
    selection=AssetSelection.all_asset_checks(),
    description="Comprobaciones de calidad sobre la matriz municipio×año.",
)

defs = Definitions(
    assets=load_assets_from_modules([assets]),
    asset_checks=COMPROBACIONES,
    jobs=[job_comprobaciones],
    schedules=SCHEDULES,
)
