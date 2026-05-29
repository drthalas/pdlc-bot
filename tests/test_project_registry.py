from app.project_registry import ProjectRegistry


def test_loads_projects_from_yaml(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
projects:
  - name: ai-sales-assistant
    aliases:
      - sales bot
      - продажи
    repo_url: https://example.com/repo.git
    local_path: /tmp/repo
    stack:
      - Python
    context_files:
      - README.md
    test_commands:
      - pytest
    risk_level: low
""",
        encoding="utf-8",
    )

    registry = ProjectRegistry(config_path)

    projects = registry.list_projects()
    assert len(projects) == 1
    assert projects[0].name == "ai-sales-assistant"
    assert projects[0].aliases == ["sales bot", "продажи"]


def test_finds_project_by_name(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text("projects:\n  - name: ai-sales-assistant\n", encoding="utf-8")
    registry = ProjectRegistry(config_path)

    assert registry.find_in_text("Please fix ai sales assistant checkout").name == "ai-sales-assistant"


def test_finds_project_by_alias(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
projects:
  - name: pdlc-bot
    aliases:
      - бот задач
""",
        encoding="utf-8",
    )
    registry = ProjectRegistry(config_path)

    assert registry.find_in_text("Создай задачу для бот задач").name == "pdlc-bot"


def test_does_not_match_inside_another_word(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
projects:
  - name: api
    aliases:
      - bot
""",
        encoding="utf-8",
    )
    registry = ProjectRegistry(config_path)

    assert registry.find_in_text("This is about apiculture and robotics") is None
