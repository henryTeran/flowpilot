"""Relocated runtime proves the Python bridge does not depend on repo/cache paths."""
from pathlib import Path
import os
import shutil
from fastapi import HTTPException
import pytest
from app.core.config import settings
from app.modules.base import upstream


def filesystem_path(value):
    # Full upstream distribution contains nested examples exceeding MAX_PATH.
    # Preserve the complete package, using Windows extended-length paths.
    return "\\\\?\\" + str(value.resolve()) if os.name == "nt" else str(value)


def test_real_upstream_runtime_at_trusted_deployment_location(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "integrations" / "base"
    target = tmp_path / "packaged-base"
    target.mkdir()
    for filename in ("runtime.mjs", "package.json", "package-lock.json"):
        shutil.copy2(source / filename, target / filename)
    shutil.copytree(source / "workspace", target / "workspace",
                    ignore=shutil.ignore_patterns("trace", "changes", "feedback", "studio.settings.json", "base.manifest.json", ".temp"))
    shutil.copytree(filesystem_path(source / "node_modules" / "@ai-swiss" / "base"),
                    filesystem_path(target / "node_modules" / "@ai-swiss" / "base"))
    assert not (target / "workspace" / ".ai" / "trace").exists()
    monkeypatch.setattr(settings, "BASE_RUNTIME_DIRECTORY", str(target))
    route = upstream.OfficialRouter().resolve("Consulter la file operationnelle")
    assert route.status == "routed" and route.process_id == "queue-read"
    assert route.context_prepared and route.framework_version == "1.5.1"


def test_missing_packaged_runtime_refuses_without_repository_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BASE_RUNTIME_DIRECTORY", str(tmp_path / "missing-runtime"))
    with pytest.raises(HTTPException) as error:
        upstream.OfficialRouter().resolve("Consulter la file operationnelle")
    assert error.value.status_code == 503
