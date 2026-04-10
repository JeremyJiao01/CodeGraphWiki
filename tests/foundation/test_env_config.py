"""Regression tests for environment configuration management.

Covers:
- 34a7ffc: reload_env single source of truth — updates present keys, removes
  absent ones, supports EMBED_* variable aliases
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from terrain.foundation.utils.settings import reload_env


class TestReloadEnv:
    """reload_env must be the single source of truth: .env file wins,
    stale shell exports are removed."""

    def test_loads_new_key_from_env_file(self, tmp_path: Path):
        """A key present in .env but not in os.environ gets set."""
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_API_KEY=sk-new-key-123\n")

        # Ensure key is not in environment
        os.environ.pop("LLM_API_KEY", None)

        result = reload_env(workspace=tmp_path)
        assert "LLM_API_KEY" in result["updated"]
        assert os.environ["LLM_API_KEY"] == "sk-new-key-123"

        # Cleanup
        os.environ.pop("LLM_API_KEY", None)

    def test_removes_stale_key(self, tmp_path: Path):
        """A key in os.environ but NOT in .env gets removed."""
        env_file = tmp_path / ".env"
        env_file.write_text("")  # Empty .env

        os.environ["LLM_API_KEY"] = "stale-value"

        result = reload_env(workspace=tmp_path)
        assert "LLM_API_KEY" in result["removed"]
        assert "LLM_API_KEY" not in os.environ

    def test_updates_changed_value(self, tmp_path: Path):
        """A key with a different value in .env gets updated."""
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_MODEL=new-model\n")

        os.environ["LLM_MODEL"] = "old-model"

        result = reload_env(workspace=tmp_path)
        assert "LLM_MODEL" in result["updated"]
        assert os.environ["LLM_MODEL"] == "new-model"

        os.environ.pop("LLM_MODEL", None)

    def test_unchanged_key_not_in_updated(self, tmp_path: Path):
        """A key with the same value in both .env and os.environ is not reported."""
        env_file = tmp_path / ".env"
        env_file.write_text("LLM_API_KEY=same-value\n")

        os.environ["LLM_API_KEY"] = "same-value"

        result = reload_env(workspace=tmp_path)
        assert "LLM_API_KEY" not in result["updated"]
        assert "LLM_API_KEY" not in result["removed"]

        os.environ.pop("LLM_API_KEY", None)

    def test_embed_star_vars_recognized(self, tmp_path: Path):
        """EMBED_API_KEY, EMBED_BASE_URL, EMBED_MODEL are config-managed."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "EMBED_API_KEY=embed-key\n"
            "EMBED_BASE_URL=http://embed.example.com\n"
            "EMBED_MODEL=embed-v1\n"
        )

        for k in ("EMBED_API_KEY", "EMBED_BASE_URL", "EMBED_MODEL"):
            os.environ.pop(k, None)

        result = reload_env(workspace=tmp_path)
        assert "EMBED_API_KEY" in result["updated"]
        assert "EMBED_BASE_URL" in result["updated"]
        assert "EMBED_MODEL" in result["updated"]

        assert os.environ["EMBED_API_KEY"] == "embed-key"
        assert os.environ["EMBED_BASE_URL"] == "http://embed.example.com"
        assert os.environ["EMBED_MODEL"] == "embed-v1"

        for k in ("EMBED_API_KEY", "EMBED_BASE_URL", "EMBED_MODEL"):
            os.environ.pop(k, None)

    def test_missing_env_file_removes_all_managed(self, tmp_path: Path):
        """If .env doesn't exist, all managed keys in os.environ are removed."""
        # Don't create .env file
        os.environ["DASHSCOPE_API_KEY"] = "will-be-removed"

        result = reload_env(workspace=tmp_path)
        assert "DASHSCOPE_API_KEY" in result["removed"]
        assert "DASHSCOPE_API_KEY" not in os.environ

    def test_non_managed_keys_untouched(self, tmp_path: Path):
        """Keys NOT in the config-managed set are never touched."""
        env_file = tmp_path / ".env"
        env_file.write_text("MY_CUSTOM_VAR=hello\n")

        os.environ["MY_CUSTOM_VAR"] = "original"

        reload_env(workspace=tmp_path)
        # MY_CUSTOM_VAR is not a managed key, so it stays unchanged
        assert os.environ["MY_CUSTOM_VAR"] == "original"

        os.environ.pop("MY_CUSTOM_VAR", None)
