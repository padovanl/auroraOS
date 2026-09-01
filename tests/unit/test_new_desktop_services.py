"""Local state, activity tracking, project workspaces and safe diagnostics."""

from types import SimpleNamespace

from aurora import activities, diagnostics, projectworkspaces
from aurora.ai import conversations
from aurora.assistant import messages_for_provider


def test_conversations_are_private_and_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    messages = [{"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"}]
    saved = conversations.upsert([], "one", messages)
    conversations.save(saved)
    assert conversations.load() == saved
    assert conversations.path().stat().st_mode & 0o777 == 0o600
    second = conversations.upsert(saved, "two", [{"role": "user", "content": "next"}])
    assert [item["id"] for item in second] == ["two", "one"]
    assert conversations.upsert(second, "one", messages)[0]["id"] == "one"


def test_attachment_context_never_goes_to_cloud_provider():
    import pytest
    messages = [{"role": "user", "content": "secret file text", "display": "📄 note.txt",
                 "local_only": True}]
    assert messages_for_provider(messages, "local") == [
        {"role": "user", "content": "secret file text"}]
    with pytest.raises(ValueError):
        messages_for_provider(messages, "openai")
    with pytest.raises(ValueError):
        messages_for_provider(messages, "anthropic")


def test_activity_progress_and_cancel(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    ident = activities.create("Copying", "copy")
    activities.update(ident, progress=0.5, item="source.txt")
    assert activities.list_recent()[0]["progress"] == 0.5
    assert not activities.cancelled(ident)
    activities.cancel(ident)
    assert activities.cancelled(ident)
    assert activities.directory().stat().st_mode & 0o777 == 0o700
    assert (activities.directory() / f"{ident}.json").stat().st_mode & 0o777 == 0o600


def test_project_workspace_uses_known_apps_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    project = tmp_path / "repo"
    project.mkdir()
    projectworkspaces.configure(str(project), editor="code", terminal=True, files=False)
    assert projectworkspaces.preferences(str(project))["editor"] == "code"
    calls = []
    monkeypatch.setattr(projectworkspaces.shutil, "which", lambda name: "/usr/bin/" + name)
    from aurora import apps
    monkeypatch.setattr(apps, "spawn", lambda argv: calls.append(argv))
    projectworkspaces.open_workspace(str(project))
    assert calls == [["code", str(project)],
                     ["ptyxis", "--new-window", "--working-directory", str(project)]]
    assert projectworkspaces.config_path().stat().st_mode & 0o777 == 0o600


def test_diagnostics_default_omits_journal_and_redacts(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    seen = []

    def run(argv, **_kwargs):
        seen.append(argv)
        return SimpleNamespace(stdout=f"{tmp_path}/doc bob@example.org token=abc", stderr="")

    monkeypatch.setattr(diagnostics.subprocess, "run", run)
    report = diagnostics.collect("boot")
    assert "journalctl" not in report
    assert "journalctl" not in [argv[0] for argv in seen]
    assert str(tmp_path) not in report
    assert "bob@example.org" not in report
    assert "token=abc" not in report
    assert "[REDACTED]" in report
    diagnostics.collect("boot", include_logs=True)
    assert "journalctl" in [argv[0] for argv in seen]
