"""Hidden notifications retain their identity and normal lifecycle under DND."""
from types import SimpleNamespace

from aurora.shell import notifications as module


def server(monkeypatch):
    class Settings:
        def get_strv(self, _key):
            return []
        def set_strv(self, _key, _value):
            pass
        def get_boolean(self, key):
            return key == 'do-not-disturb'
    monkeypatch.setattr(module.settings, 'get', lambda: Settings())
    obj = module.NotificationServer.__new__(module.NotificationServer)
    obj._next_id, obj._live, obj.history = 1, {}, []
    obj._refresh_history = lambda: None
    obj.popups = SimpleNamespace(box=SimpleNamespace(remove=lambda _card: None), sync=lambda: None)
    obj._conn = None
    def forbidden_card(*_args):
        raise AssertionError('DND must not create a popup')
    monkeypatch.setattr(module, 'Card', forbidden_card)
    calls = []
    monkeypatch.setattr(module.GLib, 'timeout_add', lambda *_args: 123)
    monkeypatch.setattr(module.GLib, 'source_remove', lambda source: calls.append(('cancel', source)))
    obj._emit = lambda signal, value: calls.append((signal, value.unpack()))
    return obj, calls


def test_dnd_replacement_updates_one_history_entry(monkeypatch):
    obj, calls = server(monkeypatch)
    first = obj.notify('Download', 0, '', 'Progress', '10%', [], {}, 5000)
    second = obj.notify('Download', first, '', 'Progress', '90%', [], {}, 5000)
    assert first == second
    assert len(obj.history) == 1 and obj.history[0].body == '90%'
    assert calls == [('cancel', 123)]


def test_dnd_notification_expires_and_closes_only_once(monkeypatch):
    obj, calls = server(monkeypatch)
    nid = obj.notify('App', 0, '', 'Message', '', [], {}, 5000)
    obj._expire(nid)
    obj.close(nid, module.REASON_CLOSED)
    assert not obj._live and len(obj.history) == 1
    assert calls == [('NotificationClosed', (nid, module.REASON_EXPIRED))]


def test_unknown_close_returns_dbus_error_without_closed_signal(monkeypatch):
    obj, calls = server(monkeypatch)
    invocation = SimpleNamespace(
        return_value=lambda value: calls.append(('reply', value)),
        return_dbus_error=lambda name, body: calls.append(('error', name, body)))
    obj._on_call(None, None, None, None, 'CloseNotification',
                 module.GLib.Variant('(u)', (99,)), invocation)
    assert calls == [('error', 'org.freedesktop.Notifications.InvalidId', '')]


def test_critical_notification_bypasses_dnd_and_has_no_expiry(monkeypatch):
    obj, calls = server(monkeypatch)
    card = object()
    shown = []
    monkeypatch.setattr(module, 'Card', lambda *_args: card)
    obj.popups.box.prepend = shown.append
    monkeypatch.setattr(module.GLib, 'timeout_add',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('critical timeout')))
    nid = obj.notify('App', 0, '', 'Critical', '', [], {'urgency': 2}, 5000)
    assert shown == [card] and obj._live[nid][1:] == (card, 0)
    obj.close(nid, module.REASON_CLOSED)
    assert calls == [('NotificationClosed', (nid, module.REASON_CLOSED))]


def test_transient_replacement_removes_old_history_and_refreshes(monkeypatch):
    obj, _calls = server(monkeypatch)
    refreshes = []
    obj._refresh_history = lambda: refreshes.append(list(obj.history))
    nid = obj.notify('App', 0, '', 'Message', '', [], {}, 0)
    assert obj._live[nid][2] == 0
    assert obj.notify('App', nid, '', 'Message', '', [], {'transient': True}, 0) == nid
    assert not obj.history and not refreshes[-1]


def test_muted_updates_retain_identity_without_history(monkeypatch):
    obj, calls = server(monkeypatch)
    prefs = module.settings.get()
    prefs.get_strv = lambda key: ['App'] if key == 'notifications-muted-apps' else []
    monkeypatch.setattr(module.settings, 'get', lambda: prefs)
    nid = obj.notify('App', 0, '', 'Message', 'first', [], {}, 1000)
    assert obj.notify('App', nid, '', 'Message', 'second', [], {}, 1000) == nid
    assert not obj.history and obj._live[nid][0].body == 'second'
    assert calls == [('cancel', 123)]
