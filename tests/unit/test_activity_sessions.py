"""Journal ordering, abandoned jobs, invalid records and login cleanup."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from aurora import activities
from aurora import surfaces
from aurora.greeter import app as greeter
from aurora.settingsapp import system


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path))
    return activities.directory()


def test_running_work_is_not_hidden_by_recent_completions(journal):
    active = activities.create('Long copy', 'copy')
    for n in range(25):
        ident = activities.create(f'Completed {n}', 'copy')
        activities.update(ident, status='finished')
    assert activities.list_recent()[0]['id'] == active
    assert len(activities.list_recent(limit=None)) == 26


def test_dead_or_reused_process_is_interrupted(journal):
    ident = activities.create('Copy', 'copy')
    activities.update(ident, owner_start='wrong-start-time')
    item = activities.list_recent()[0]
    assert item['status'] == 'failed' and item['interrupted']


def test_clear_preserves_active_jobs_and_removes_cancel_markers(journal):
    active = activities.create('Copy', 'copy')
    done = activities.create('Old copy', 'copy')
    activities.cancel(done)
    activities.update(done, status='cancelled')
    activities.clear_finished()
    assert [item['id'] for item in activities.list_recent()] == [active]
    assert not activities.cancelled(done)


def test_cancel_ignores_finished_or_non_cancellable_records(journal):
    done = activities.create('Done', 'copy')
    activities.update(done, status='finished')
    protected = activities.create('Protected', 'install', cancellable=False)
    for ident in (done, protected, 'missing'):
        activities.cancel(ident)
        assert not activities.cancelled(ident)


def test_malformed_fields_do_not_crash_the_panel(journal):
    good = activities.create('Good', 'copy')
    for n, fields in enumerate(({'updated': 'yesterday'}, {'label': {}},
                                 {'updated': float('nan')}, {'status': 'unknown'})):
        ident = f'bad{n}'
        (journal / f'{ident}.json').write_text(json.dumps(
            {'id': ident, 'status': 'finished', 'updated': 1, **fields}))
    activities.update(good, progress='invalid')
    assert [item['id'] for item in activities.list_recent()] == [good]
    assert activities.list_recent()[0]['progress'] == 0


def test_update_recovers_a_non_mapping_record(journal):
    ident = activities.create('Copy', 'copy')
    (journal / f'{ident}.json').write_text('[]')
    activities.update(ident, label='Recovered', status='finished')
    assert activities.list_recent()[0]['label'] == 'Recovered'


def test_separate_users_runtime_journals_do_not_mix(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path / 'user-a'))
    a = activities.create('Private A', 'copy')
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path / 'user-b'))
    b = activities.create('Private B', 'copy')
    activities.cancel(a)
    assert [item['id'] for item in activities.list_recent()] == [b]
    monkeypatch.setenv('XDG_RUNTIME_DIR', str(tmp_path / 'user-a'))
    assert not activities.cancelled(a)


def test_primary_sudo_group_is_an_administrator(monkeypatch):
    monkeypatch.setattr(system.grp, 'getgrnam', lambda _name: SimpleNamespace(gr_mem=[], gr_gid=27))
    monkeypatch.setattr(system.pwd, 'getpwnam', lambda _name: SimpleNamespace(pw_gid=27))
    assert system.is_admin('admin')


def test_custom_surface_colors_yield_to_high_contrast(monkeypatch):
    provider = Mock()
    monkeypatch.setattr(surfaces, '_provider', provider)
    surfaces._load(SimpleNamespace(get_high_contrast=lambda: True))
    provider.load_from_string.assert_called_once_with('')


@pytest.mark.parametrize('timeout', [0, 1])
def test_password_change_closes_pty_on_timeout_and_exit(monkeypatch, timeout):
    closed, killed = [], []
    monkeypatch.setattr(system, 'pty', SimpleNamespace(fork=lambda: (999999, 77)))
    monkeypatch.setattr(system, 'select', SimpleNamespace(select=lambda *_args: ([77], [], [])))
    monkeypatch.setattr(system, 'os', SimpleNamespace(
        read=lambda *_args: b'', waitpid=lambda *_args: (999999, 0),
        close=closed.append, kill=lambda *args: killed.append(args),
        WIFEXITED=os.WIFEXITED, WEXITSTATUS=os.WEXITSTATUS))
    ok, _message = system.change_password('old', 'new', timeout=timeout)
    assert closed == [77]
    assert ok == bool(timeout)
    assert bool(killed) == (timeout == 0)


def test_switching_greeter_account_clears_previous_password():
    obj = SimpleNamespace(password=Mock(), _selected_user=lambda: None,
                          username=Mock(), avatar=Mock())
    greeter.Greeter._on_user(obj)
    obj.password.set_text.assert_called_once_with('')


@pytest.mark.parametrize('failure', [False, True])
def test_login_closes_protocol_socket_on_success_and_failure(monkeypatch, failure):
    client = Mock()
    client.create_session.return_value = {'type': 'error', 'description': 'auth failed'} if failure else {'type': 'success'}
    client.start_session.return_value = {'type': 'success'}
    monkeypatch.setattr(greeter, 'Greetd', lambda: client)
    callbacks = []
    monkeypatch.setattr(greeter.GLib, 'idle_add', lambda callback, *args: callbacks.append((callback, args)))
    obj = SimpleNamespace(_done=Mock(), _failed=Mock())
    greeter.Greeter._authenticate(obj, 'user-a', 'test-password', 'aurora-session labwc')
    client.close.assert_called_once_with()
    assert callbacks[-1][0] is (obj._failed if failure else obj._done)
