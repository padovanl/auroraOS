"""Desktop widgets: the saved list, placement, sizes and the dev/gamer parsers."""

from aurora.shell import devwidgets, widgets


def test_load_list_keeps_valid_entries_only():
    text = ('[{"kind": "clock", "x": 0.5, "y": 2}, {"kind": "nope"}, "junk",'
            ' {"kind": "notes", "id": "../../etc"}, {"kind": "gpu", "x": "a"}]')
    items = widgets.load_list(text)
    assert items[0] == {"kind": "clock", "x": 0.5, "y": 1.0}     # clamped to the screen
    assert [i["kind"] for i in items] == ["clock", "notes"]
    assert items[1]["id"].isalnum()                              # no path in a note id
    assert widgets.load_list("not json") == []
    assert widgets.load_list(widgets.dump_list(items)) == items


def test_widgets_stay_on_screen_clear_of_the_top_bar():
    assert widgets.clamp_position(-50, -50, 170, 170, 1920, 1080, top=44, edge=12) == (12, 44)
    assert widgets.clamp_position(1900, 1000, 170, 170, 1920, 1080, top=44, edge=12) == (
        1920 - 170 - 12, 1080 - 170 - 12)
    assert widgets.snap(23) == 16 and widgets.snap(25) == 32


def test_widget_size_follows_the_screen_height():
    assert widgets.widget_sizes(1080) == (170, 356)
    small_4k, _ = widgets.widget_sizes(2160)
    assert small_4k == 256                     # capped
    assert widgets.widget_sizes(768)[0] == 156  # still readable on small screens
    assert widgets.widget_sizes(1440)[0] > 170


def test_dropped_widget_lines_up_with_a_neighbour():
    other = (1600, 100, 170, 170)
    # Near the column: same left edge; near the bottom: one gap below.
    assert widgets.align_to_neighbours(1606, 285, 170, 170, [other]) == (1600, 286)
    # Far from everything: unchanged (the grid decides).
    assert widgets.align_to_neighbours(400, 500, 170, 170, [other]) == (400, 500)


def test_month_grid_and_first_weekday():
    weeks = widgets.month_grid(2026, 9, 0)          # September 2026 starts on a Tuesday
    assert weeks[0][:3] == [0, 1, 2]
    assert sum(1 for w in weeks for d in w if d) == 30
    assert all(len(w) == 7 for w in weeks)
    assert widgets.month_grid(2026, 9, 6)[0][:3] == [0, 0, 1]   # weeks start on Sunday
    assert widgets.first_weekday("first_weekday=2\nweek-1stday=19971130") == 0   # Monday
    assert widgets.first_weekday("first_weekday=1\nweek-1stday=19971130") == 6   # Sunday


def test_dev_widget_parsers():
    status = ("# branch.oid abc\n# branch.head main\n# branch.ab +2 -1\n"
              "1 .M N... 100644 100644 100644 a b src/x.py\n? new.txt\n")
    assert devwidgets.parse_git_status(status) == ("main", 2, 1, 2)
    assert devwidgets.parse_git_status("") == ("", 0, 0, 0)
    acf = '"AppState"\n{\n\t"appid"\t\t"570"\n\t"name"\t\t"Dota 2"\n\t"LastPlayed"\t"17"\n}'
    assert devwidgets.parse_acf(acf)["name"] == "Dota 2"
    assert devwidgets.parse_nvidia("RTX 4070, 35, 61, 2048, 12282") == (
        "RTX 4070", 35.0, 61.0, 2048.0, 12282.0)
    assert devwidgets.parse_nvidia("[N/A]") is None


def test_steam_games_skip_tools(tmp_path):
    apps = tmp_path / "Steam" / "steamapps"
    apps.mkdir(parents=True)
    (apps / "appmanifest_1.acf").write_text('"appid" "1"\n"name" "Hades"\n"LastPlayed" "20"')
    (apps / "appmanifest_2.acf").write_text('"appid" "2"\n"name" "Proton 9.0"\n"LastPlayed" "30"')
    (apps / "appmanifest_3.acf").write_text('"appid" "3"\n"name" "Celeste"\n"LastPlayed" "40"')
    games = devwidgets.steam_games(roots=(str(tmp_path / "Steam"),))
    assert [g[1] for g in games] == ["Celeste", "Hades"]


def test_windows_keep_their_proportions_after_a_resolution_change():
    from aurora.shell.refit import floating, refit_geometry
    old = {"x": 0, "y": 30, "width": 2560, "height": 1380}
    new = {"x": 0, "y": 30, "width": 1280, "height": 690}
    window = {"x": 1280, "y": 330, "width": 1200, "height": 900}
    assert refit_geometry(window, old, new) == {"x": 640, "y": 180, "width": 600, "height": 450}
    # Never below the app's minimum size, and still fully on screen.
    small = refit_geometry(window, old, new, min_size=(800, 600))
    assert (small["width"], small["height"]) == (800, 600)
    assert small["x"] + 800 <= 1280 and small["y"] + 600 <= 720
    assert refit_geometry(window, old, old) == window
    assert floating({"role": "toplevel", "mapped": True, "tiled-edges": 0})
    assert not floating({"role": "toplevel", "mapped": True, "tiled-edges": 15})
    assert not floating({"role": "toplevel", "mapped": True, "fullscreen": True})


def test_local_servers_from_ss():
    text = ('LISTEN 0 511 127.0.0.1:5173 0.0.0.0:* users:(("node",pid=41,fd=20))\n'
            'LISTEN 0 128 0.0.0.0:22 0.0.0.0:*\n'
            'LISTEN 0 4096 [::]:8000 [::]:* users:(("python3",pid=7,fd=3))\n'
            'LISTEN 0 4096 [::1]:5173 [::]:* users:(("node",pid=41,fd=21))\n'
            'LISTEN 0 4096 192.168.1.5:9000 0.0.0.0:*\n')
    assert devwidgets.parse_listening(text) == [(5173, "node"), (8000, "python3")]
    assert devwidgets.parse_listening("") == []


def test_gallery_lists_every_widget_once():
    assert len(set(widgets.KIND_NAMES)) == len(widgets.KIND_NAMES) == 23
    assert set(widgets.KIND_NAMES) == set(widgets.kinds())


def test_gauge_colour_follows_the_accent_then_warns():
    accent = (0.66, 0.44, 1.0)
    assert widgets.usage_color(0.3, accent) == accent            # the user's theme
    amber = widgets.usage_color(0.85, accent)
    assert amber == (1.0, 0.64, 0.36)
    red = widgets.usage_color(1.0, accent)
    assert red[0] == 1.0 and red[1] < 0.4                         # rose-red when full
    halfway = widgets.usage_color(0.725, accent)
    assert accent[1] < halfway[1] < amber[1]


def test_widget_options_are_saved_and_sanitised():
    text = ('[{"kind": "clock", "options": {"style": "digital", "bad": [1, 2]}},'
            ' {"kind": "photo", "options": "nope"}]')
    items = widgets.load_list(text)
    assert items[0]["options"] == {"style": "digital"}
    assert "options" not in items[1]
