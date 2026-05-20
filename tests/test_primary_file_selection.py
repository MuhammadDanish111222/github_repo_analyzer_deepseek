from pydantic import SecretStr

from app.core.config import Settings
from app.services.github_service import GitHubRepositoryService


def make_service() -> GitHubRepositoryService:
    settings = Settings(deepseek_api_key=SecretStr("test-key"))
    return GitHubRepositoryService(settings)


def test_selects_main_python_over_test_file():
    service = make_service()
    tree = [
        {"type": "blob", "path": "tests/test_app.py", "size": 3000},
        {"type": "blob", "path": "main.py", "size": 5000},
        {"type": "blob", "path": "README.md", "size": 1000},
    ]

    selected = service.select_primary_file(tree)

    assert selected is not None
    assert selected["path"] == "main.py"


def test_ignores_node_modules_and_minified_files():
    service = make_service()
    tree = [
        {"type": "blob", "path": "node_modules/pkg/index.js", "size": 5000},
        {"type": "blob", "path": "dist/app.min.js", "size": 5000},
        {"type": "blob", "path": "src/server.ts", "size": 5000},
    ]

    selected = service.select_primary_file(tree)

    assert selected is not None
    assert selected["path"] == "src/server.ts"
