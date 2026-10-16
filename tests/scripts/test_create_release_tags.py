import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/create-release-tags"
VERSION = "0.1.0a8"


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


@pytest.fixture
def release_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "xolo-client").mkdir()
    (repo / "xolo-ui").mkdir()
    shutil.copy2(SCRIPT, repo / "scripts/create-release-tags")
    (repo / "pyproject.toml").write_text(f'[tool.poetry]\nversion = "{VERSION}"\n')
    (repo / "xolo-client/pyproject.toml").write_text(f'[tool.poetry]\nversion = "{VERSION}"\n')
    (repo / "xolo-ui/VERSION").write_text(f"{VERSION}\n")
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Release Test")
    git(repo, "config", "user.email", "release@example.test")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "Prepare release")
    return repo


def run_script(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(repo / "scripts/create-release-tags"), *args],
        cwd=repo,
        text=True,
        capture_output=True,
    )


def test_creates_three_local_annotated_tags(release_repo: Path) -> None:
    result = run_script(release_repo, VERSION)
    assert result.returncode == 0, result.stderr
    for component in ("api", "client", "ui"):
        tag = f"{component}-v{VERSION}"
        assert git(release_repo, "cat-file", "-t", f"refs/tags/{tag}") == "tag"
        assert git(release_repo, "rev-list", "-n", "1", tag) == git(release_repo, "rev-parse", "HEAD")
    assert run_script(release_repo, VERSION).returncode != 0


def test_rejects_version_mismatch_and_uncommitted_changes(release_repo: Path) -> None:
    assert "Version mismatch" in run_script(release_repo, "0.1.0a9").stderr
    (release_repo / "xolo-ui/VERSION").write_text("0.1.0a9\n")
    assert "Version mismatch" in run_script(release_repo, VERSION).stderr
    (release_repo / "xolo-ui/VERSION").write_text(f"{VERSION}\n")
    (release_repo / "uncommitted.txt").write_text("not released\n")
    assert "not clean" in run_script(release_repo, VERSION).stderr
    assert git(release_repo, "tag", "--list") == ""


def test_pushes_all_three_tags_to_origin(release_repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    git(release_repo, "remote", "add", "origin", str(remote))
    result = run_script(release_repo, VERSION, "--push")
    assert result.returncode == 0, result.stderr
    remote_tags = git(release_repo, "ls-remote", "--tags", "--refs", "origin")
    for component in ("api", "client", "ui"):
        assert f"refs/tags/{component}-v{VERSION}" in remote_tags
