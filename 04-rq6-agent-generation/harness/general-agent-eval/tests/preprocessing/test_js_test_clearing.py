from __future__ import annotations

from pathlib import Path

import pytest

from general_agent_eval.preprocessing.js_test_clearing import (
    clear_js_tests,
)
from general_agent_eval.preprocessing.java_test_clearing import TestClearingError


def write_file(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_clear_js_tests_removes_test_directories(tmp_path: Path) -> None:
    write_file(tmp_path / "cypress/e2e/login.cy.ts")
    write_file(tmp_path / "e2e/navigation.spec.ts")
    write_file(tmp_path / "__tests__/App.test.tsx")
    write_file(tmp_path / "tests/fixtures/data.json")
    write_file(tmp_path / "src/App.tsx", "export default function App() {}")

    result = clear_js_tests(tmp_path)

    removed_paths = {item.path for item in result.removed}
    assert "cypress" in removed_paths
    assert "e2e" in removed_paths
    assert "__tests__" in removed_paths
    assert "tests" in removed_paths
    assert not (tmp_path / "cypress").exists()
    assert not (tmp_path / "e2e").exists()
    assert not (tmp_path / "__tests__").exists()
    assert not (tmp_path / "tests").exists()


def test_clear_js_tests_preserves_production_files(tmp_path: Path) -> None:
    write_file(tmp_path / "src/App.tsx", "export default function App() {}")
    write_file(tmp_path / "package.json", "{}")
    write_file(tmp_path / "vite.config.ts", "export default {}")
    write_file(tmp_path / "cypress/e2e/login.cy.ts")

    clear_js_tests(tmp_path)

    assert (tmp_path / "src/App.tsx").exists()
    assert (tmp_path / "package.json").exists()
    assert (tmp_path / "vite.config.ts").exists()


def test_clear_js_tests_removes_test_files_by_pattern(tmp_path: Path) -> None:
    write_file(tmp_path / "src/utils.test.ts")
    write_file(tmp_path / "src/Button.spec.jsx")
    write_file(tmp_path / "src/Login.cy.js")
    write_file(tmp_path / "src/App.tsx")

    result = clear_js_tests(tmp_path)

    removed_paths = {item.path for item in result.removed}
    assert "src/utils.test.ts" in removed_paths
    assert "src/Button.spec.jsx" in removed_paths
    assert "src/Login.cy.js" in removed_paths
    assert not (tmp_path / "src/utils.test.ts").exists()
    assert not (tmp_path / "src/Button.spec.jsx").exists()
    assert not (tmp_path / "src/Login.cy.js").exists()
    assert (tmp_path / "src/App.tsx").exists()


def test_clear_js_tests_prunes_node_modules(tmp_path: Path) -> None:
    # Vendored tests inside node_modules must not be removed.
    write_file(tmp_path / "node_modules/some-lib/__tests__/index.test.js")
    write_file(tmp_path / "src/App.tsx")

    result = clear_js_tests(tmp_path)

    assert (tmp_path / "node_modules/some-lib/__tests__/index.test.js").exists()
    assert not any("node_modules" in item.path for item in result.removed)


def test_clear_js_tests_prunes_dist(tmp_path: Path) -> None:
    # dist/ is a build artifact; *.test.js files inside it must not be removed.
    write_file(tmp_path / "dist/assets/App.test.js")
    write_file(tmp_path / "src/App.tsx")

    result = clear_js_tests(tmp_path)

    assert (tmp_path / "dist/assets/App.test.js").exists()
    assert not any("dist" in item.path for item in result.removed)


def test_clear_js_tests_skips_git_metadata(tmp_path: Path) -> None:
    write_file(tmp_path / ".git/hooks/pre-push")
    write_file(tmp_path / "cypress/e2e/login.cy.ts")

    clear_js_tests(tmp_path)

    assert (tmp_path / ".git/hooks/pre-push").exists()
    assert not (tmp_path / "cypress").exists()


def test_clear_js_tests_to_dict_shape(tmp_path: Path) -> None:
    write_file(tmp_path / "cypress/e2e/login.cy.ts")

    manifest = clear_js_tests(tmp_path).to_dict()

    assert manifest["removed_count"] == 1
    assert manifest["preserved_suspicious_count"] == 0
    assert manifest["preserved_suspicious"] == []
    removed = manifest["removed"]
    assert len(removed) == 1
    assert removed[0]["path"] == "cypress"
    assert removed[0]["kind"] == "directory"


def test_clear_js_tests_empty_project_returns_empty_result(tmp_path: Path) -> None:
    write_file(tmp_path / "src/App.tsx")
    write_file(tmp_path / "package.json", "{}")

    result = clear_js_tests(tmp_path)

    assert result.removed == ()
    assert result.preserved_suspicious == ()


def test_clear_js_tests_rejects_missing_root(tmp_path: Path) -> None:
    with pytest.raises(TestClearingError, match="Root does not exist"):
        clear_js_tests(tmp_path / "missing")
