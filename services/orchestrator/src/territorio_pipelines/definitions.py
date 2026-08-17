from dagster import Definitions, load_assets_from_modules

from territorio_pipelines import assets
from territorio_pipelines.schedules import SCHEDULES

defs = Definitions(assets=load_assets_from_modules([assets]), schedules=SCHEDULES)
