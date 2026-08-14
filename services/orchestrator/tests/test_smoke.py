def test_definitions_load():
    """El grafo de assets debe cargar sin errores y contener los nodos clave."""
    from territorio_pipelines.definitions import defs

    names = {key.to_user_string() for key in defs.resolve_asset_graph().get_all_asset_keys()}
    # La dimensión de la que cuelga todo, una fuente y una salida de modelo.
    assert "dim_municipio" in names
    assert "padron" in names
    assert "prediccion_ml" in names


def test_no_quedan_assets_stub():
    """Ningún asset debe limitarse a loguear y devolver 0.

    `matriz_municipio_anual` estuvo así durante meses, declarado en la documentación
    como "el objetivo del MVP" mientras la fusión la hacían de facto los loaders.
    """
    import inspect

    from territorio_pipelines import assets

    for nombre, obj in vars(assets).items():
        fn = getattr(obj, "op", None)
        fn = getattr(fn, "compute_fn", None)
        decorada = getattr(fn, "decorated_fn", None)
        if decorada is None:
            continue
        fuente = inspect.getsource(decorada)
        assert "STUB" not in fuente, f"el asset {nombre} sigue siendo un stub"
