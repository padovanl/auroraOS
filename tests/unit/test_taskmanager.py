"""Task Manager helpers: /proc parsing, grouping into apps, startup apps."""

import os

from aurora import procinfo as p


def test_stat_with_odd_names():
    text = "1234 (Web Content (x)) S 1000 1234 1234 0 -1 4194560 10 0 0 0 150 50 0 0 20 0 7 0 99 0 0"
    name, state, ppid, ticks, threads, start = p.parse_stat(text)
    assert (name, state, ppid, ticks, threads, start) == ("Web Content (x)", "S", 1000, 200, 7, 99)


def test_app_is_found_from_environment_or_cgroup():
    env = b"HOME=/h\0GIO_LAUNCHED_DESKTOP_FILE=/usr/share/applications/firefox-esr.desktop\0"
    assert p.app_from_environ(env) == "firefox-esr.desktop"
    assert p.app_from_environ(b"HOME=/h\0") is None
    cg = "0::/user.slice/user-1000.slice/user@1000.service/app.slice/app-flatpak-org.gimp.GIMP-4521.scope"
    assert p.app_from_cgroup(cg) == "org.gimp.GIMP.desktop"
    assert p.app_from_cgroup("0::/user.slice/session-2.scope") is None
    assert p.parse_io("rchar: 5\nread_bytes: 4096\nwrite_bytes: 1024\n") == 5120


def _proc(pid, ppid, uid, app=None):
    x = p.Process(pid)
    x.ppid, x.uid, x.app = ppid, uid, app
    return x


def test_children_join_their_parents_app():
    procs = {1: _proc(1, 0, 0), 10: _proc(10, 1, 1000, "firefox.desktop"),
             11: _proc(11, 10, 1000), 12: _proc(12, 11, 1000), 20: _proc(20, 1, 1000)}
    g = p.group(procs, uid=1000)
    assert sorted(x.pid for x in g["apps"]["firefox.desktop"]) == [10, 11, 12]
    assert [x.pid for x in g["background"]] == [20]
    assert [x.pid for x in g["system"]] == [1]


def test_startup_apps_can_be_turned_off_without_touching_the_system(tmp_path):
    system, user = tmp_path / "xdg", tmp_path / "user"
    system.mkdir()
    (system / "sync.desktop").write_text("[Desktop Entry]\nName=Sync\nExec=sync-daemon\n")
    (system / "kde.desktop").write_text("[Desktop Entry]\nName=K\nExec=k\nOnlyShowIn=KDE;\n")
    entries = p.startup_entries(str(user), [str(system)])
    assert [e["name"] for e in entries] == ["Sync"] and entries[0]["enabled"]
    p.set_startup(entries[0], False, str(user), [str(system)])
    entries = p.startup_entries(str(user), [str(system)])
    assert entries[0]["enabled"] is False and entries[0]["exec"] == "sync-daemon"
    assert "Hidden=" not in (system / "sync.desktop").read_text()
    p.set_startup(entries[0], True, str(user), [str(system)])
    assert p.startup_entries(str(user), [str(system)])[0]["enabled"]


def test_sampler_reads_this_process():
    s = p.Sampler()
    s.sample(1)
    procs = s.sample(1)
    me = procs[os.getpid()]
    assert me.rss > 0 and me.cpu >= 0


def test_apps_are_what_has_a_window():
    procs = {10: _proc(10, 1, 1000, "kdeconnect.desktop"), 20: _proc(20, 1, 1000),
             21: _proc(21, 20, 1000)}
    g = p.group(procs, uid=1000, windows={20: "org.gnome.Calculator"})
    assert sorted(x.pid for x in g["apps"]["org.gnome.Calculator"]) == [20, 21]
    assert [x.pid for x in g["background"]] == [10]


def test_readable_process_names():
    x = p.Process(1)
    x.name, x.cmdline = "python3", "/usr/bin/python3 /usr/bin/aurora-shell --gapplication"
    assert p.display_name(x) == "aurora-shell"
    x.name, x.cmdline = "aurora-taskmana", "/usr/bin/aurora-taskmanager"
    assert p.display_name(x) == "aurora-taskmanager"
    x.name, x.cmdline = "wayfire", "wayfire -c x"
    assert p.display_name(x) == "wayfire"
