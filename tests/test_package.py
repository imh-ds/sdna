def test_package_imports():
    import sdna

    assert isinstance(sdna.__version__, str)
