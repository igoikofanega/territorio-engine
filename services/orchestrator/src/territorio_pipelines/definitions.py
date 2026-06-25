from dagster import Definitions, load_assets_from_modules

from territorio_pipelines import assets

defs = Definitions(assets=load_assets_from_modules([assets]))
