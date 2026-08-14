import zipfile

import pytest

from src.personality.zip_security import is_safe_zip_member, validate_zip_archive


class TestIsSafeZipMember:
    def test_safe_members(self):
        assert is_safe_zip_member("manifest.yaml") is True
        assert is_safe_zip_member("phrases/greeting.yaml") is True

    @pytest.mark.parametrize(
        "name",
        [
            "../evil.yaml",
            "a/../../b",
            "\\..\\evil",
            "C:\\windows\\system32",
        ],
    )
    def test_unsafe_members(self, name):
        assert is_safe_zip_member(name) is False


class TestValidateZipArchive:
    def test_valid_pack(self, tmp_path):
        pack = tmp_path / "pack.zip"
        with zipfile.ZipFile(pack, "w") as zf:
            zf.writestr("manifest.yaml", "name: Tomo\n")
            zf.writestr("phrases/hello.yaml", "greeting: hi\n")
        assert validate_zip_archive(pack) is True

    def test_missing_manifest(self, tmp_path):
        pack = tmp_path / "pack.zip"
        with zipfile.ZipFile(pack, "w") as zf:
            zf.writestr("phrases/hello.yaml", "greeting: hi\n")
        assert validate_zip_archive(pack) is False

    def test_traversal_member(self, tmp_path):
        pack = tmp_path / "pack.zip"
        with zipfile.ZipFile(pack, "w") as zf:
            zf.writestr("manifest.yaml", "name: Tomo\n")
            zf.writestr("../escape.yaml", "bad\n")
        assert validate_zip_archive(pack) is False

    def test_absolute_ish_member(self, tmp_path):
        pack = tmp_path / "pack.zip"
        with zipfile.ZipFile(pack, "w") as zf:
            zf.writestr("manifest.yaml", "name: Tomo\n")
            zf.writestr(zipfile.ZipInfo("..\\x"), "bad\n")
        assert validate_zip_archive(pack) is False

    def test_not_a_zip(self, tmp_path):
        bogus = tmp_path / "bogus.zip"
        bogus.write_text("not a zip at all")
        assert validate_zip_archive(bogus) is False

    def test_missing_path(self, tmp_path):
        missing = tmp_path / "does_not_exist.zip"
        assert validate_zip_archive(missing) is False

    def test_oversized_archive(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.personality.zip_security.MAX_PACK_ZIP_SIZE", 10)
        big = tmp_path / "big.zip"
        big.write_bytes(b"x" * 20)
        assert validate_zip_archive(big) is False
