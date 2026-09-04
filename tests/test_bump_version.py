"""Tests del gestor de versiones ``build/bump_version.py``."""

import importlib.util
import re
from pathlib import Path

import pytest

_BUILD_DIR = Path(__file__).resolve().parent.parent / "build"


def _load_bump_version():
    path = _BUILD_DIR / "bump_version.py"
    spec = importlib.util.spec_from_file_location("bump_version", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bump():
    return _load_bump_version()


class TestCurrentVersion:
    def test_returns_semver_shape(self, bump):
        assert re.fullmatch(r"\d+\.\d+\.\d+", bump.current_version())


class TestValidateSemver:
    def test_accepts_patch_component(self, bump):
        bump.validate_semver("1.0.1")

    def test_accepts_minor_component(self, bump):
        bump.validate_semver("2.14.3")

    def test_rejects_missing_patch(self, bump):
        with pytest.raises(ValueError):
            bump.validate_semver("1.1")

    def test_rejects_v_prefix(self, bump):
        with pytest.raises(ValueError):
            bump.validate_semver("v1.1.0")

    def test_rejects_prerelease_suffix(self, bump):
        with pytest.raises(ValueError):
            bump.validate_semver("1.1.0-beta")


class TestNewSrcInit:
    def test_replaces_version(self, bump):
        src = '__version__ = "1.0.0"\n'
        assert bump.new_src_init(src, "1.1.0") == '__version__ = "1.1.0"\n'

    def test_raises_when_version_missing(self, bump):
        with pytest.raises(ValueError):
            bump.new_src_init("x = 1\n", "1.1.0")


class TestNewReadme:
    SAMPLE = (
        "![Version](https://img.shields.io/badge/version-1.0.0-blue)\n"
        "![Status](https://img.shields.io/badge/status-v1.0.0--release-yellow)\n"
    )

    def test_updates_both_badges(self, bump):
        out = bump.new_readme(self.SAMPLE, "1.1.0")
        assert "badge/version-1.1.0-blue" in out
        assert "badge/status-v1.1.0--release" in out
        assert "1.0.0" not in out

    def test_raises_when_badges_missing(self, bump):
        with pytest.raises(ValueError):
            bump.new_readme("no badges here", "1.1.0")