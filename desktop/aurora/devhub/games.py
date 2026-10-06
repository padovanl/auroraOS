"""Game Hub catalog: games, Windows apps and Android apps, one click each.

Steam, Heroic, Bottles and ProtonUp-Qt come from Flathub (sandboxed, always
current, with their own graphics runtime). GameMode, MangoHud and Lutris are
Debian packages. Waydroid comes from its official repository.
"""

from aurora.devhub.recipes import APT_REPO, flatpak, flatpak_check
from aurora.i18n import N_

CATEGORIES = [
    ("stores", N_("Game Stores")),
    ("windows", N_("Windows Apps and Games")),
    ("tools", N_("Performance Tools")),
    ("android", N_("Android Apps")),
]

RECIPES = [
    {"id": "steam", "cat": "stores", "name": "Steam", "icon": "com.valvesoftware.Steam",
     "fallback_icon": "applications-games",
     "desc": N_("Valve's store. Proton runs most Windows games; turn it on in Steam Play."),
     "check": flatpak_check("com.valvesoftware.Steam"),
     "script": flatpak("com.valvesoftware.Steam")},
    {"id": "heroic", "cat": "stores", "name": "Heroic Games Launcher",
     "icon": "com.heroicgameslauncher.hgl", "fallback_icon": "applications-games",
     "desc": N_("Epic Games, GOG and Amazon Prime Gaming libraries in one launcher."),
     "check": flatpak_check("com.heroicgameslauncher.hgl"),
     "script": flatpak("com.heroicgameslauncher.hgl")},
    {"id": "lutris", "cat": "stores", "name": "Lutris", "icon": "lutris",
     "fallback_icon": "applications-games",
     "desc": N_("Install scripts for thousands of games, emulators included."),
     "check": "command -v lutris",
     "script": "sudo apt-get update && sudo apt-get install -y lutris"},
    {"id": "bottles", "cat": "windows", "name": "Bottles", "icon": "com.usebottles.bottles",
     "fallback_icon": "wine", "desc": N_("Run Windows programs in tidy, separate Wine bottles."),
     "check": flatpak_check("com.usebottles.bottles"),
     "script": flatpak("com.usebottles.bottles")},
    {"id": "protonup", "cat": "windows", "name": "ProtonUp-Qt", "icon": "net.davidotek.pupgui2",
     "fallback_icon": "applications-games",
     "desc": N_("Install newer Proton-GE and Wine-GE builds for Steam, Lutris and Heroic."),
     "check": flatpak_check("net.davidotek.pupgui2"),
     "script": flatpak("net.davidotek.pupgui2")},
    {"id": "gamemode", "cat": "tools", "name": "GameMode", "icon": "applications-games",
     "fallback_icon": "applications-games",
     "desc": N_("Feral's daemon: the CPU and GPU run at full speed while you play."),
     "check": "command -v gamemoderun",
     "script": "sudo apt-get update && sudo apt-get install -y gamemode"},
    {"id": "mangohud", "cat": "tools", "name": "MangoHud", "icon": "utilities-system-monitor",
     "fallback_icon": "utilities-system-monitor",
     "desc": N_("Frame rate, temperatures and load on top of your games."),
     "check": "command -v mangohud",
     "script": "sudo apt-get update && sudo apt-get install -y mangohud"},
    {"id": "waydroid", "cat": "android", "name": "Waydroid", "icon": "waydroid",
     "fallback_icon": "phone",
     "desc": N_("Android in a container, with its apps in your dock. Needs about 1 GB."),
     "check": "command -v waydroid",
     "script": APT_REPO + r'''
add_repo waydroid https://repo.waydro.id/waydroid.gpg "Types: deb
URIs: https://repo.waydro.id/
Suites: trixie
Components: main"
sudo apt-get install -y waydroid
sudo waydroid init
sudo systemctl enable --now waydroid-container
echo 'Waydroid is ready: open it from Launchpad.'
'''},
]

GAME_HUB = {
    "id": "org.aurora.GameHub", "title": N_("Game Hub"), "search": N_("Search games and tools"),
    "hero": N_("Play anything"),
    "text": N_("Steam with Proton runs most Windows games. Add the Epic and GOG stores, "
               "Windows programs with Bottles, and Android apps with Waydroid, each with one "
               "click."),
    "categories": CATEGORIES, "recipes": RECIPES,
}
