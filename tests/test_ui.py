"""Verificación de la interfaz en un navegador real. Se salta si no hay playwright o chromium."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

pytestmark = pytest.mark.ui


def test_cero_errores_de_consola(capsys):
    pytest.importorskip("playwright.sync_api")
    import capturas
    try:
        codigo = capturas.principal(verificar=True)
    except Exception as e:  # chromium sin instalar, sin permisos, etc.
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            pytest.skip("chromium no está instalado")
        raise
    salida = capsys.readouterr().out
    assert codigo == 0, salida
    for estado in capturas.ESTADOS:
        assert f"{estado}: 0 errores" in salida
