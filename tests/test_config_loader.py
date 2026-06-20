"""Config-loader validation: errors are raised on load, naming the problem."""

from __future__ import annotations

import pytest

from backend.app import config_loader
from backend.app.config_loader import ConfigError
from tests._helpers import write_tmp_config


def test_agent_id_must_match_filename(tmp_path):
    s = write_tmp_config(tmp_path)
    (s.agents_dir / "a.yaml").write_text(
        "id: wrong\nname: A\ndescription: d\nsystem_prompt: p\noutput_schema: {type: object}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        config_loader.load_agent("a", s)


def test_missing_agent_file_raises(tmp_path):
    s = write_tmp_config(tmp_path)
    with pytest.raises(ConfigError):
        config_loader.load_agent("nope", s)


def test_crew_referencing_unknown_worker(tmp_path):
    s = write_tmp_config(tmp_path)
    (s.crews_dir / "t_crew.yaml").write_text(
        "id: t_crew\nname: T\nworkers: [a, ghost]\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        config_loader.load_crew("t_crew", s)


def test_plan_referencing_non_worker(tmp_path):
    s = write_tmp_config(tmp_path)
    (s.crews_dir / "t_crew.yaml").write_text(
        "id: t_crew\nname: T\nworkers: [a, b]\n"
        "execution_plan:\n  - agent: a\n    depends_on: [ghost]\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        config_loader.load_crew("t_crew", s)


def test_invalid_yaml_names_file(tmp_path):
    s = write_tmp_config(tmp_path)
    (s.agents_dir / "a.yaml").write_text("id: a\nname: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        config_loader.load_agent("a", s)
