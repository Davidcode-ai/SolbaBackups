"""
Tests del módulo de configuración.
"""

from pathlib import Path

from src.config.settings import Settings, _DEFAULTS


class TestSettingsDefaults:
    def test_default_compression(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert s.compression == _DEFAULTS["compression"]

    def test_default_retention(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert s.retention_days == _DEFAULTS["retention_days"]

    def test_backup_dir_is_path(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert isinstance(s.backup_dir, Path)

    def test_databases_is_list(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert isinstance(s.databases, list)


class TestSettingsYAML:
    def test_load_from_yaml(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("compression: tar.gz\nretention_days: 7\n")
        s = Settings(config_path=cfg)
        assert s.compression == "tar.gz"
        assert s.retention_days == 7

    def test_nested_yaml(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("google_drive:\n  enabled: true\n  folder_id: abc123\n")
        s = Settings(config_path=cfg)
        assert s.google_drive["enabled"] is True
        assert s.google_drive["folder_id"] == "abc123"

    def test_save_and_reload(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        save_path = tmp_path / "saved.yaml"
        s.save(save_path)
        assert save_path.exists()
        s2 = Settings(config_path=save_path)
        assert s2.compression == s.compression


class TestSettingsEnvOverrides:
    def test_env_override_compression(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOLBA_COMPRESSION", "none")
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert s.compression == "none"

    def test_env_override_retention(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SOLBA_RETENTION_DAYS", "90")
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        assert s.retention_days == 90


class TestSettingsGet:
    def test_get_nested(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text("google_drive:\n  enabled: false\n")
        s = Settings(config_path=cfg)
        val = s.get("google_drive", "enabled")
        assert val is False

    def test_get_default_fallback(self, tmp_path):
        s = Settings(config_path=tmp_path / "nonexistent.yaml")
        val = s.get("nonexistent_key", default="fallback")
        assert val == "fallback"
