"""Tests de los metadatos de empaquetado (``tomodesk.spec`` y version info).

Cubren tres regresiones reales del build de Windows:

- El exe salia sin recurso ``RT_VERSION`` porque ``tomodesk.spec`` calculaba
  ``version`` y nunca lo pasaba a ``EXE()``.
- ``data/comments_*.yaml`` no viajaba en el bundle, asi que ``CommentLoader``
  arrancaba con ``phrases = {}`` y el usuario empaquetado se quedaba sin
  comentarios ambientales.
- ``build/version_info.txt`` (generado) podia quedar desincronizado con
  ``src/__init__.py``.
"""

import ast
import importlib.util
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = _ROOT / "tomodesk.spec"
_BUILD_DIR = _ROOT / "build"


def _load_make_version_info():
    path = _BUILD_DIR / "make_version_info.py"
    spec = importlib.util.spec_from_file_location("make_version_info", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def spec_tree():
    return ast.parse(_SPEC.read_text(encoding="utf-8"), filename=str(_SPEC))


@pytest.fixture(scope="module")
def resources(spec_tree):
    """La lista ``_RESOURCES`` del spec, evaluada como literal."""
    for node in spec_tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "_RESOURCES":
                return [tuple(pair) for pair in ast.literal_eval(node.value)]
    raise AssertionError("No se encontro _RESOURCES en tomodesk.spec")


@pytest.fixture(scope="module")
def exe_call(spec_tree):
    for node in ast.walk(spec_tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "EXE":
            return node
    raise AssertionError("No se encontro la llamada a EXE() en tomodesk.spec")


class TestVersionResource:
    """El .exe debe llevar el recurso RT_VERSION (parametro version= de EXE)."""

    def test_exe_passes_version_keyword(self, exe_call):
        keywords = {kw.arg for kw in exe_call.keywords}
        assert "version" in keywords, (
            "EXE() no recibe version=; el exe saldria sin recurso RT_VERSION"
        )

    def test_generator_emits_the_src_version(self):
        """`make_version_info` deriva el semver de ``src/__init__.py``."""
        make_version_info = _load_make_version_info()
        current = make_version_info._current_version()
        text = make_version_info._build(current)

        major, minor, patch = (int(p) for p in current.split("."))
        assert f"filevers=({major}, {minor}, {patch}, 0)" in text
        assert f"prodvers=({major}, {minor}, {patch}, 0)" in text
        assert f"StringStruct('FileVersion', '{current}.0')" in text

    def test_version_info_file_is_not_stale_when_present(self):
        """``build/version_info.txt`` es un artefacto de build (en .gitignore).

        Se compara solo si existe: en un clon limpio o en el job de tests de CI
        todavia no se ha generado, y eso no es un fallo.
        """
        version_info = _BUILD_DIR / "version_info.txt"
        if not version_info.exists():
            pytest.skip("build/version_info.txt es un artefacto de build (gitignored)")

        make_version_info = _load_make_version_info()
        expected = make_version_info._build(make_version_info._current_version())
        assert version_info.read_text(encoding="utf-8") == expected, (
            "build/version_info.txt esta desincronizado con src/__init__.py; "
            "regeneralo con `python build/make_version_info.py`"
        )


class TestBundledResources:
    def test_every_resource_source_exists(self, resources):
        missing = [src for src, _dst in resources if not (_ROOT / src).exists()]
        assert missing == [], f"Recursos del spec que no existen: {missing}"

    def test_resource_policy_defaults_are_bundled(self, resources):
        """Cada clave de `paths` con base de recursos tiene su entrada en el spec.

        Sin esto, una ruta de solo lectura resuelta contra `resource_dir()`
        apunta a un archivo que no viaja en el bundle.
        """
        from src.config import paths

        bundled = {src for src, _dst in resources}
        resource_base = getattr(paths, "_RESOURCE")
        missing = []
        for keys, (base, default) in paths._PATH_POLICY.items():
            if base != resource_base:
                continue
            if default not in bundled:
                missing.append((keys, default))
        assert missing == [], (
            "Claves de config resueltas contra resource_dir() sin entrada en "
            f"_RESOURCES: {missing}"
        )

    def test_all_comment_locale_files_are_bundled(self, resources):
        """CommentLoader deriva `comments_<idioma>.yaml` de la ruta base.

        Por eso no basta con empaquetar el archivo por defecto: la variante de
        cada idioma tambien tiene que viajar.
        """
        bundled = {src for src, _dst in resources}
        on_disk = {p.name for p in (_ROOT / "data").glob("comments_*.yaml")}
        assert on_disk, "No hay data/comments_*.yaml en el checkout"
        missing = sorted(
            name for name in on_disk if f"data/{name}" not in bundled
        )
        assert missing == [], f"Archivos de comentarios sin empaquetar: {missing}"


class TestLlamaCppGuard:
    """El spec debe poder exigir el provider local (asset con IA local)."""

    def test_require_flag_is_honored(self, spec_tree):
        source = _SPEC.read_text(encoding="utf-8")
        assert "TOMODESK_REQUIRE_LLAMA_CPP" in source, (
            "tomodesk.spec no lee TOMODESK_REQUIRE_LLAMA_CPP: un release podria "
            "salir sin el provider de IA local"
        )
        # El fallo debe ser explicito (SystemExit), no un aviso silencioso.
        raisers = [
            node
            for node in ast.walk(spec_tree)
            if isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and getattr(node.exc.func, "id", None) == "SystemExit"
        ]
        assert raisers, "El spec no aborta el build cuando falta llama-cpp-python"


class TestBuildScriptsInstallLocalAiByDefault:
    """Los scripts de build incluyen la IA local salvo que se pida lo contrario."""

    @pytest.mark.parametrize(
        "script, opt_out",
        [("build_windows.ps1", "-Standard"), ("build_unix.sh", "--standard")],
    )
    def test_script_installs_llama_cpp_and_declares_opt_out(self, script, opt_out):
        text = (_BUILD_DIR / script).read_text(encoding="utf-8")
        assert "requirements-llama.txt" in text, (
            f"{script} ya no instala requirements-llama.txt"
        )
        assert "TOMODESK_REQUIRE_LLAMA_CPP" in text, (
            f"{script} no exporta TOMODESK_REQUIRE_LLAMA_CPP"
        )
        assert opt_out in text, f"{script} no ofrece {opt_out} para omitirlo"
        # La instalacion no debe quedar condicionada a una bandera --full/-Full.
        assert not re.search(r"--full\b", text) or "obsoleto" in text.lower(), (
            f"{script} sigue exigiendo --full para incluir la IA local"
        )
