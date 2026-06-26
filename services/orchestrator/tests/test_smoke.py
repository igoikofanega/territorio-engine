def test_definitions_load():
    """El grafo de assets debe cargar sin errores y contener la matriz objetivo."""
    from territorio_pipelines.definitions import defs

    names = {key.to_user_string() for key in defs.resolve_asset_graph().get_all_asset_keys()}
    assert "matriz_municipio_anual" in names
    assert "dim_municipio" in names
