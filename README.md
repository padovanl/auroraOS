<div align="center">

<img src="docs/aurora-boot.png" width="180" alt="Aurora OS boot animation">

# Aurora OS

[![Latest release](https://img.shields.io/github/v/release/padovanl/auroraOS?display_name=release&label=release)](https://github.com/padovanl/auroraOS/releases/latest)
[![Release downloads](https://img.shields.io/github/downloads/padovanl/auroraOS/latest/total?label=release%20asset%20downloads)](https://github.com/padovanl/auroraOS/releases/latest)
[![License](https://img.shields.io/github/license/padovanl/auroraOS)](LICENSE)
[![Release ISO](https://img.shields.io/github/actions/workflow/status/padovanl/auroraOS/release-iso.yml?label=ISO%20build)](https://github.com/padovanl/auroraOS/actions/workflows/release-iso.yml)

**A beautiful, developer-ready Linux distribution built on Debian.**

A calm macOS-inspired desktop written from scratch, the tools developers use every day
preinstalled, and the rock-solid Debian 13 base underneath.

**[Documentation](https://padovanl.github.io/auroraOS/manual/)** ·
[Website](https://padovanl.github.io/auroraOS/) ·
[Install guide](https://padovanl.github.io/auroraOS/install.html)

</div>

---

## Contents

1. [What Aurora OS is](#what-aurora-os-is) · [why I build it](#why-i-build-it)
2. [Why Aurora is different](#why-aurora-is-different)
3. [Features](#features)
4. [Get started (users)](#get-started-users) · [try it in QEMU](#try-it-in-a-virtual-machine-qemu) · [on Hyper-V, with your GPU for AI](HYPERV.md)
5. [Using Aurora](#using-aurora)
6. [Build it yourself](#build-it-yourself)
7. [How we built Aurora OS: making a Linux distribution, step by step](#how-we-built-aurora-os-making-a-linux-distribution-step-by-step)
8. [How it works (architecture)](#how-it-works-architecture)
9. [Under the hood: every technical choice](#under-the-hood-every-technical-choice)
10. [Versions, updates and the kernel](#versions-updates-and-the-kernel)
11. [Testing](#testing)
12. [Customizing](#customizing)
13. [Languages](#languages)
14. [Repository layout](#repository-layout)
15. [Known limitations and roadmap](#known-limitations-and-roadmap)
16. [License and credits](#license-and-credits)

---

## What Aurora OS is

Aurora OS is a **Linux distribution**: the Linux kernel and the Debian 13 "trixie" userland,
plus everything that makes it *Aurora*: its own desktop environment, apps, installer
configuration, branding, defaults and developer tooling. It relates to Debian the way Ubuntu
does: same package format (`.deb`), same repositories and security updates, with a different
experience on top.

It ships as a single ISO image that you write to a USB stick. From there you can **try** it
live without touching your disk, or **install** it with a guided installer. It runs on
laptops, desktops and virtual machines, with BIOS or UEFI firmware.

### Why I build it

Ever since I was a child I've been fascinated by programming. It's what I chose to study,
and it's what I've built my whole working life around. Over all those years one question
never went away: *what does it actually take to make an operating system?* Not an app,
but the whole thing: a computer that starts up, installs itself and greets you with a
desktop you'd enjoy using every day.

Aurora is my attempt at an answer, built just for fun: to understand every layer, from the
firmware handing over to the boot loader up to the pixels of the dock, and to make, along
the way, the desktop I'd want for myself. It stands on Debian; everything above it is
written for Aurora, and every bug we hit is written down with how we fixed it, because
learning was the point. — *Luca Padovan*

## Why Aurora is different

- **Its own desktop, not a re-skin.** The panel, dock, launcher, notifications, control
  center, settings, file manager, login screen and welcome app are written from scratch for
  Aurora (Python + GTK 4 on Wayland), about 10,000 lines you can read and change.
- **Beautiful by default.** A macOS-inspired layout: a menu bar, a floating dock with
  magnification, Spotlight-style search, a Launchpad grid and round colored window buttons
  that always show what they do (close, minimize, expand/restore).
  All of it uses our own artwork.
- **A private AI assistant, built in, off until you want it.** Aurora AI runs a language
  model **on your computer** (nothing leaves it) or uses Claude or any OpenAI-compatible
  service with your key. Ask from Spotlight with `?`, get commands in the terminal with
  `ask` and `why`, fix and rewrite any text with Writing Tools, dictate with
  <kbd>Super</kbd>+<kbd>H</kbd>, have text read aloud, and find documents by what they're
  about. Every place it appears has its own switch, and it answers in your language.
- **Made for developers, but not bloated.** Git, compilers, Python, Node.js, Docker, Podman,
  distrobox, a modern shell and a pretty terminal work out of the box. Heavier toolchains
  (VS Code, Rust, Go, Java, Kubernetes, Terraform, databases) are **one click away in Dev
  Hub**, always installed from their official source at their latest version.
- **Customizable for real.** One click switches between four layout presets (Aurora, Classic,
  Studio, Minimal). Past that, the panel and dock can go at the bottom or on either side, be
  floating or full width, auto-hide or magnify, and you pick icon size, window buttons,
  corner radius, fonts, themes, pointer and accent color.
- **Stable underneath, and you can always go back.** Debian's security team, Debian's
  packages, a 6.12 LTS kernel. On top of that, Aurora installs on **btrfs** and takes a
  **snapshot before every update**: if an update ever breaks something, choose "Aurora OS
  snapshots" in the boot menu and start yesterday's system.
- **Small things that feel like a Mac**, which no other distribution puts together:
  Quick Look (press <kbd>Space</kbd> on a file), a wallpaper that follows the sun, dark
  style at sunset, copy text out of any screenshot, clipboard history and emoji in
  Spotlight, unit and currency conversion, window overview and hot corners, your phone's
  notifications on the desktop, touchpad gestures, AirDrop-style sharing with any phone
  or computer, and startup and shutdown sounds.
- **Games and Windows apps without fiddling.** Game Hub installs Steam (with Proton),
  Heroic (Epic, GOG), Lutris, Bottles for Windows programs and Waydroid for Android apps,
  one click each.
- **It looks after itself.** Settings → System Health checks disks (including SMART),
  space, updates, firmware, drivers, services, the firewall, snapshots and the battery,
  and fixes each problem with one click. Laptops can stop charging at 80% to keep the
  battery young.
- **Features people asked the big distros for**, included by default:
  - Flatpak with Flathub enabled (not only snaps);
  - the firewall on out of the box, with a switch in Settings;
  - automatic security updates;
  - compressed RAM swap (zram);
  - system snapshots before every update, bootable from the GRUB menu;
  - a real per-user "log in automatically" switch;
  - custom keyboard shortcuts in Settings;
  - SSH that you turn on with one switch;
  - a Settings search built into the launcher;
  - no telemetry, no ads in the terminal, no snaps forced on you.
- **Tested before every release.** Unit tests, a headless desktop smoke test, image checks,
  real boots in BIOS and UEFI virtual machines, and a real installation driven through the
  installer's own screens (see [Testing](#testing)).

## Features

### Desktop
| | |
|---|---|
| **Menu bar** | Aurora menu (who you are and the computer's name; About, Settings, App Center, Dev Hub, System Health, Force Quit with their shortcuts; Lock; Sleep, Restart, Shut Down and Log Out as round buttons), the focused app's name (with the number of its windows when there are several; a click lists them, numbered, to switch, plus New Window, Minimize, Close and Quit), an icon for each minimized window (click to bring it back), the Aurora Assistant button, Spotlight, an optional **system monitor** (processor and memory at a glance; its popover adds temperature, download and upload speed, free disk space; Settings → Desktop & Dock → Top Bar), status icons, clock. Menus opened with a shortcut close with <kbd>Esc</kbd>. |
| **Dock** | Pinned and running apps with one mark per open window (up to three; the window you're in is a short bar in the accent color), drag-to-reorder pinned apps, right-click menus (windows, New Window, app actions, keep/remove), Launchpad, Trash with "Empty Trash". Rest the pointer on an app with several windows to see them and pick one; a minimized one is listed as such and one click brings it back. Apps that are only open can be left out entirely, so the top bar's window buttons are the single list of what is running. Magnification, bottom/left/right, and it gets out of the way the way other docks do: by default it keeps no strip of screen, so a maximized window uses the whole display and the dock slides away until the pointer reaches the edge (or never, or always). Three styles: one floating shelf, islands of glass (Launchpad, the apps and the Trash each on their own pill, like the top bar's floating style) or a full-width taskbar. |
| **Spotlight** (tap <kbd>Super</kbd>) | One search for apps, settings pages, recent files, git projects, a calculator (`12*(3+4)`), unit and currency conversion (`10 km in mi`, `100 usd in eur`), emoji (`:rocket`), clipboard history (`clip:` or <kbd>Super</kbd>+<kbd>V</kbd>), questions for the AI (`? …`), documents by meaning (when turned on), commands (`> htop`), system actions (`restart`, `lock`, `empty trash`, `task manager`…), the time anywhere (`time in Tokyo`), paths (`~/Doc…`, `/etc`), web addresses (`github.com`) and the web. |
| **Rounded screen corners** | The display is shaped like modern hardware: four small surfaces round the corners of every monitor, without taking a single click. 0 to 24 px in Settings → Desktop & Dock. |
| **Launchpad** | Full-screen grid of every app, in sections: Frequently Used (what Screen Time counted over the last week), then Internet, Office, Photos, Music & Video, Games, Development and Utilities, each alphabetical. Type to search instead. |
| **Overview** (<kbd>Super</kbd>+<kbd>W</kbd>) | Every open window as a card over a blurred desktop: type to filter, click to switch, × or middle-click to close, "Show Desktop". |
| **Touchpad gestures** | Three fingers up for all windows, down for the desktop, sideways to change workspace; pinch with four fingers for Launchpad. |
| **Hot corners** | Push the pointer into a corner to show all windows, Launchpad, the desktop, Control Center, notifications, lock or turn off the screen. Bottom left shows all windows and bottom right the desktop by default; change them in Settings → Multitasking. |
| **Desktop widgets** | Twenty-three glanceable cards on the desktop, in five groups. Everyday: clock (analog or digital), calendar, weather, world clock, sun & moon (sunrise, sunset, daylight and the moon's phase), photo frame, now playing. Productivity: to-do list, notes, countdown to a date (with its own colors), focus timer, progress of the day, week, month or year, recent files, clipboard. System: gauges for processor, memory, disk and temperature that turn from your accent color to amber and red as they fill, network speed, battery. Developers: Git projects, local dev servers (click to open in the browser), containers. Gamers: Steam games, GPU, power profile. Drag them anywhere (a guide shows where they land and they line up with their neighbours), right-click for **Customize…**, and **Edit Widgets…** on the desktop's menu: open windows step aside until you're done, and a compact gallery with one tab per group adds widgets in the first free spot. They follow the accent color, light or dark style, clock format and units, and keep their place and proportions when the resolution changes. |
| **Quick Look** | Select a file in Files and press <kbd>Space</kbd>: pictures, video and audio, PDF pages, source code with syntax highlighting, folders. Arrows move to the next file. |
| **Dynamic wallpaper** | The Aurora landscape changes through the day (dawn, day, dusk, night) and crossfades from one to the next, in three series to choose from: Starfall, Veil and Horizon. The login and lock screens follow it. |
| **Backgrounds** | Settings → Appearance works like Windows' Personalize page: a preview of the desktop, then **Dynamic** (follows the sun), **Picture** (the ones used lately, Browse Photos…, and All Wallpapers…, a searchable gallery that stays quick with thousands of pictures), **Picture of the day** (Bing, NASA's APOD or Wikimedia Commons, with title and credit), **Slideshow** (any folder, every 15 minutes to 24 hours, shuffled if you like) or a **Solid color**. The lock screen follows the active picture. |
| **Automatic dark style** | "Auto" in Settings → Appearance switches to dark at sunset and back at sunrise. |
| **Night Light** | Warmer colors from sunset to sunrise, on a schedule you set, or all the time. Where the graphics driver can't change the screen's colors (virtual machines), it says so instead of doing nothing. |
| **Screenshots** | <kbd>Print</kbd>, <kbd>Shift</kbd>+<kbd>Print</kbd> for an area. The notification offers **Pin to Screen** (the screenshot floats above every window; drag it, scroll to resize, double-click to unpin; also <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> for an area), **Annotate** (arrows, text, highlighter, blur) and **Copy Text**. Screen recording covers the whole screen or an area, with or without the computer's sound (<kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>R</kbd>, <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd> for an area). <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>T</kbd> copies the text inside any area of the screen (offline OCR in 18 languages). <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> is a **color picker**: click any pixel and its hex code is copied. |
| **Weather** | Current weather and the next hours next to the calendar and in the weather widget (can be turned off), for the city chosen in GNOME Weather, else its automatic location, else the time zone's city; a new city shows at once. |
| **Sounds** | An Aurora sound when you log in and when you shut down, restart or log out (on by default, Settings → Sound). |
| **Control Center** | Laid out like macOS' Control Center: dark frosted glass, the time and date on top, slim sliders with the level in percent, and the toggles grouped in quiet cards (Connections, Modes, Screen), each a round icon that fills with your accent color when on. Output volume and device, microphone and input device, brightness; Wi-Fi (network list, passwords), Wired, Bluetooth (devices, with the battery of headphones, mice and keyboards), Power Mode, Night Light, Dark Style, Do Not Disturb, **Keep Awake** (no screen blanking, locking or automatic suspend until turned off), Airplane Mode, **Mobile Hotspot** (share the connection over Wi-Fi, with name, password and a QR code to join), Screen Keyboard (Aurora's own, in ten themes: Aurora, Light, Accent Color, Glass, Mechanical, Comic, Typewriter, Synthwave, Pixel, Candy, some with their own key shapes and lettering), Screen Recording; media controls for whatever is playing; battery time, screenshot, settings, lock and power. Scroll over the top bar's status icons to change the volume, middle-click to mute. A **Show Desktop** sliver at the far end of the bar hides every window and brings them back, as on Windows. Caps Lock and Num Lock show their state on screen; a Bluetooth device low on battery gets a warning. |
| **Notifications** | Freedesktop-compatible server, popups with actions, history in the calendar popover with Do Not Disturb and Clear. **Automatic Do Not Disturb**, like Windows' Focus Assist: on a schedule, while an app is fullscreen, while sharing or recording the screen. A one-time code in a notification ("Your code is 482913") gets a **Copy 482913** button. |
| **System tray** | StatusNotifierItem icons (Discord, Slack, Steam, Dropbox, Nextcloud…) in the top bar, with their menus. |
| **Desktop icons** | Files in the Desktop folder appear on the background: click or draw a selection rectangle to select several, Ctrl-click to add or remove, double-click to open, or drag an icon to any free position. Positions persist between sessions. New icons fill columns from the top left or right, folders first; app launchers (`.desktop` files) show their app name and icon. |
| **Windows** | Wayfire manages the default **Aurora** session, with snapping to halves and quarters, workspaces and a window switcher. **Snap Layouts** (<kbd>Super</kbd>+<kbd>Z</kbd>) as in Windows 11: six layouts (halves, two thirds, thirds, half and quarters, quarters, a wide middle), a preview where the window will go, then **Snap Assist** offers the other windows for the empty spaces; snapping to a half with <kbd>Super</kbd>+<kbd>←</kbd>/<kbd>→</kbd> offers the other half the same way. **Always on Top** with <kbd>Super</kbd>+<kbd>T</kbd>. On Hyper-V's display, which has no 3D, Wayfire draws with software rendering and llvmpipe runs without worker threads, so every frame is complete when Hyper-V's driver copies it to the screen. `labwc` in `~/.config/aurora/compositor` switches to labwc. **Aurora Compatibility** always uses labwc, and labwc also takes over if Wayfire cannot start, leaving a startup report in System Health. GTK apps keep Aurora's styled title bars. |
| **Animations** | Wayfire animates opening, closing, minimization and restoration of windows. Settings → Appearance can turn the compositor effects and GTK/Files transitions off together. The labwc fallback has GTK/Files transitions only. |
| **Aurora icons** | Aurora's own icon theme: apps, folders (violet, with an emblem for Home, Downloads, Music…), drives and file types (a page with a glyph and a label: PDF, PY, ZIP, DOC…), all drawn by code. Well-known brands (Firefox, LibreOffice, Steam, VS Code…) keep their own icons. |
| **Login** | Graphical greeter on greetd, optional automatic login, lock screen, idle screen-off. |
| **Boot** | Branded GRUB menu and an animated Plymouth splash (the logo draws itself). |
| **One look everywhere** | libadwaita apps, GTK 3 apps (adw-gtk3), plain GTK 4 apps, Qt apps (QGnomePlatform), window decorations and icons all follow the light/dark style and accent color you pick. |

### Apps written for Aurora
- **Settings**: everything Ubuntu's Settings has, and more:
  - **Network** (share Wi-Fi with a QR code, VPNs), **Bluetooth**, **Displays** (resolution
    and refresh rate, scale, rotation).
  - **Sound**: devices, volume, left/right balance, over-amplification, session sounds, and a
    **Volume Mixer** with each app's own volume (also in the Control Center).
  - **Power**: screen blank, automatic suspend on battery and when plugged in, what the
    power button and the lid do, power mode, battery percentage, battery health, 80%
    charge limit, and **Battery Saver**, which turns on by itself below 20% (or a level you
    choose) and off when you plug in.
  - **Appearance**: style, accent, wallpaper gallery with large preview, icons, pointer, fonts, Night Light,
    animations and window animations. **Desktop & Dock** (layouts, top bar, dock, window
    buttons, desktop icons, what Spotlight shows), **Multitasking**, **Desktop Profiles**
    (Work, Gaming, Battery and custom combinations of dock, notifications, effects and power).
  - **Notifications**: Do Not Disturb, notifications per app, what happens when a drive is
    connected. **Apps**: default and startup apps.
  - **Mouse & Touchpad** (gestures), **Keyboard** (repeat, Compose key for special
    characters, custom shortcuts), **Printers**.
  - **Accessibility**: high contrast, text size, pointer size, reduced animation, always
    visible scrollbars, screen reader, **zoom** (whole screen or a lens,
    <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>8</kbd>), alert sounds, **screen keyboard**,
    blinking cursor, double-click delay.
  - **Privacy & Security** (screen lock, file history, searchable clipboard history
    with pins and image entries, weather, firewall), **App Permissions** (review and revoke
    remembered Flatpak portal grants), **Sharing** (screen sharing, nearby sharing, phone, SSH), **AI**.
  - **Users** (profile card and picture, fingerprint, **online accounts** for Google, Microsoft, Nextcloud…),
    Language & Region, Date & Time, Software Updates (system snapshots), **System
  Health** with guided, user-reviewed diagnostic reports for installation, startup and apps,
    **Storage** (what takes the space, one-click cleanup and **Storage Sense**, which empties
    old Trash items, temporary files and unused Downloads by itself), **Screen Time** (each
    app's time, the week as bars, daily limits with a reminder), restarts after updates like
    Windows (**Restart Now**, **Tonight**, active hours, optional automatic restart with a
    warning), About.
- **Aurora Assistant**: chat with the AI, with quick actions on copied text (summarize,
  improve, translate, explain), code blocks you can copy, answers read aloud. Chats are
  saved locally; you can stop or regenerate an answer. New replies scroll into view unless
  you are reading earlier messages: then a highlighted animated down-arrow lets you jump
  to the latest reply. Attach text, code, documents and photos with the paperclip or by
  dragging them into chat (photos are read with offline OCR). Attachments only go to a
  model **on your computer or your network** (Ollama, LM Studio), never to a cloud
  provider; switching providers requires a new chat. Pick the model from the title; with
  none installed yet, it says how to get one. The Assistant floats
  **like a picture-in-picture video**: a card in the bottom-right corner, just above the
  dock (right at the bottom when the dock is hidden or on a side), above your other
  windows and on every workspace. It never takes the keyboard from the app you are using
  unless you click it or open it with <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd>.
  Minimize it to a small bar like a chat on a web page (a dot shows a new reply), expand
  it for long answers, close it with × when you're done. And
  **Writing Tools** for selected text anywhere (<kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>).
- **Task Manager** (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Esc</kbd>): apps (what has a window,
  with its processes folded underneath), background and system processes with CPU, memory
  and disk, End Task and Kill; performance graphs; startup apps with a switch each; system
  and user services with start, stop and restart.
- **Files**: places and drives, **Network** (shared folders that announce themselves) and **Connect to
  Server…** (smb, sftp, ftp, WebDAV), **Compress…** (zip, 7z, tar.xz) and **Extract Here**,
  **Resize Images…** (like PowerToys' Image Resizer), **What's Using This?** (which programs
  hold a file that's “in use”, and end them), **Copy Path**,
  grid and list views with drag-to-select, search, hidden files, cut/copy/paste
  with progress, cancel and retry, trash with restore, rename, new folder, "Open With", properties, open in
  terminal, batch rename, SHA-256 checksums, two-folder comparison, Git change badges,
  **Quick Look** (<kbd>Space</kbd>), "Send to Nearby Device" and, with AI,
  "Summarize", "Ask About This File" and a reviewed Git-change summary.
- **Dev Hub**: about 90 one-click installers in 17 categories, with a category sidebar
  and search. Its Project Workspaces open the configured editor, terminal and Files together
  for each repository or folder. In the animated session they can also save and restore
  window positions; Compatibility opens the apps without moving windows. Tool installs and AI downloads appear alongside file
  transfers in the panel's **Activities** menu. The installer catalog covers editors and
  IDEs, languages and runtimes, cloud and DevOps, databases and
  API tools, AI assistants (Claude Code, Codex, Ollama), **shells and terminals** (Zsh,
  Oh My Zsh, fish, default-shell switch, Starship, Zellij, kitty, Alacritty, WezTerm,
  Tilix, Terminator, GNOME Console), command-line tools, version control, containers and
  virtual machines, web, mobile, debugging and performance, data science, game
  development, embedded and hardware, design and documentation, security and networking.
- **Game Hub**: Steam, Heroic, Lutris, Bottles, ProtonUp-Qt, GameMode, MangoHud, Waydroid.
- **Welcome**: first-run tour (light or dark, shortcuts, install).

### Preinstalled software
- **Developers:** git, git-lfs, lazygit, delta, build-essential, gdb, cmake, shellcheck,
  Python (pip, venv, pipx), Node.js and npm, Docker (+ compose, buildx), Podman, distrobox,
  neovim, tmux, ripgrep, fd, fzf, bat, btop, jq, httpie, direnv, tldr, starship, zsh,
  JetBrains Mono and Fira Code, **[portop](https://github.com/padovanl/portop)** (see
  which process holds a port and stop it with one key) and
  **[pkgtui](https://github.com/padovanl/pkgtui)** (search, install, remove and upgrade
  apt, Flatpak and Snap packages from one terminal UI).
- **Everyday** (the same set of apps Ubuntu ships): Firefox, Geary Mail, LibreOffice
  (Writer, Calc, Impress), Calendar, Contacts, Weather, Maps, Clocks, Calculator, Text
  Editor, Image Viewer, Document Viewer (PDF), Music (Rhythmbox), Videos (Celluloid, with
  codecs), Camera, Sound Recorder, Document Scanner, Backups (Déjà Dup), Remote Desktop
  (Remmina), Transmission, Archive Manager, Disks, Disk Usage, Logs,
  Characters, Fonts, Power Statistics, Firmware, Passwords and Keys, App Center (GNOME
  Software with Flatpak), and **LocalSend** for sending files to any nearby device.
- The full list, with what the tests check for each app, is in
  [`config/apps.manifest`](config/apps.manifest).
- **Transmission** (torrents) never starts by itself, and ships with the public peer network
  (DHT), local peer discovery, peer exchange and router port opening turned off, so opening it
  contacts nobody until you switch them on in its Preferences. Company firewalls flag even a
  client's first DHT contact as BitTorrent traffic.
- **Anything else** is one click away in App Center, which covers the whole Debian archive
  (tens of thousands of packages) and Flathub. Nothing is installed without you asking.

### Hardware
- Firmware for Intel, AMD, Realtek, Atheros, Broadcom and MediaTek Wi-Fi and Bluetooth,
  GPUs and audio (SOF).
- Mesa with Vulkan and VA-API video acceleration, the Intel media driver, NVIDIA detection.
- Laptops: power profiles, thermald, screen rotation, firmware updates (fwupd), backlight
  and battery, battery health and an **80% charge limit** on laptops whose firmware
  supports it (ThinkPad, ASUS, Dell, Framework, Huawei, LG, Samsung, System76…).
- **Fingerprint readers:** set up your finger in Settings → Users, then use it instead of
  the password for `sudo` and admin prompts.
- **Your phone:** KDE Connect (Android and iPhone) shows the phone's notifications on the
  desktop and shares files and the clipboard. Turn it on in Settings → Sharing.
- VMs: QEMU/KVM guest agent and SPICE, VMware tools, Hyper-V daemons.
- Printing (CUPS, driverless IPP) and scanning, Bluetooth manager.
- **Additional Drivers** (Settings → Software Updates) detects NVIDIA cards and installs the
  recommended proprietary driver.
- **VPNs:** WireGuard, OpenVPN and OpenConnect through NetworkManager's connection editor
  (Settings → Network → VPN and Advanced).

### Installer
The installer is Calamares with Aurora's look: the steps across the top as dots that fill
in as you go, one filled "Next" button, roomy pages. It walks you through language,
location and time zone (detected automatically), keyboard, disk, user and a summary. On
the keyboard page, **Detect…** finds your layout with two or three questions about what
is printed on your keys (which letters start the top row, which character is next to L). For
the disk you can erase it, install alongside another OS, replace a partition, or partition
by hand. It supports LUKS encryption and btrfs (the default, with automatic snapshots),
ext4 or xfs. On the user page you set your
name, user name, password and computer name, and choose **automatic login** or the login
screen. Everything the installer needs is on the USB stick, so it **works offline**.

## Get started (users)

### 1. Get the ISO
Build it (see [Build it yourself](#build-it-yourself)), or download a release when they are
published. GitHub limits release files to 2 GB, so larger ISOs are published in numbered
parts: download every `.iso.part-*` file and join them before checking the download:
```sh
cat aurora-os-VERSION-amd64.iso.part-* > aurora-os-VERSION-amd64.iso
```
```sh
sha256sum -c aurora-os-VERSION-amd64.iso.sha256
```

### Try it in a virtual machine (QEMU)
No USB stick needed: boot the ISO in QEMU/KVM on any Linux computer.

```sh
sudo apt install qemu-system-x86 qemu-utils ovmf   # Debian/Ubuntu; "qemu-kvm edk2-ovmf" on Fedora
```

**From this repository**, the quickest way:
```sh
make run          # live system in a QEMU window (BIOS)
make run-uefi     # the same with UEFI firmware
```
`build/run-qemu.sh` takes a few options for everything else:
```sh
build/run-qemu.sh --uefi --disk aurora.qcow2 aurora-os-VERSION-amd64.iso   # install on a 40 GB virtual disk
build/run-qemu.sh --uefi --disk aurora.qcow2 ''                        # start the installed system
build/run-qemu.sh --software aurora-os-VERSION-amd64.iso                   # no 3D, like Hyper-V
```
With `--uefi --disk`, the firmware's boot entries are kept in `aurora.qcow2.vars`, as on
a real PC.

**Just the ISO**, with no repository:
```sh
qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 4 -m 4G \
  -cdrom aurora-os-VERSION-amd64.iso -boot d \
  -device virtio-vga-gl -display gtk,gl=on \
  -device intel-hda -device hda-duplex \
  -nic user,model=virtio-net-pci -usb -device usb-tablet
```
- `-device virtio-vga-gl -display gtk,gl=on` gives the VM 3D acceleration, and Wayfire
  uses the host's GPU. If your host can't do that (for example over SSH), use `-vga std
  -display gtk`: Wayfire then draws on the CPU, as on Hyper-V. (`-device virtio-vga`
  without `-gl` starts labwc instead: Mesa won't draw on the CPU there, see
  [Bugs we found](#bugs-we-found-and-how-we-fixed-them).)
- `usb-tablet` makes the pointer follow your mouse without capturing it.
- Add `-drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd` to
  boot with UEFI (on Fedora the file is `/usr/share/edk2/ovmf/OVMF_CODE.fd`).

**Install it on a virtual disk** and boot the installed system:
```sh
qemu-img create -f qcow2 aurora.qcow2 40G
# 1. boot the ISO with the disk attached, then run "Install Aurora OS" from the dock
qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 4 -m 4G \
  -cdrom aurora-os-VERSION-amd64.iso -boot d \
  -drive file=aurora.qcow2,if=virtio \
  -device virtio-vga-gl -display gtk,gl=on -nic user,model=virtio-net-pci -usb -device usb-tablet
# 2. after the installer finishes, start from the disk (no -cdrom)
qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 4 -m 4G \
  -drive file=aurora.qcow2,if=virtio \
  -device virtio-vga-gl -display gtk,gl=on -nic user,model=virtio-net-pci -usb -device usb-tablet
```
Keep the same firmware (BIOS or UEFI, with the same `-drive if=pflash…` line) for the
installation and for later boots.

**On a Linux server, watched from another computer**: a QEMU window over `ssh -Y` is
slow, since every frame travels as X11. Serve the screen with SPICE on the server
instead, and open it through an SSH tunnel:
```sh
# on the server (inside tmux or screen, so it keeps running)
build/run-qemu.sh --uefi --disk aurora.qcow2 --spice 5930 aurora-os-VERSION-amd64.iso
# on your computer (Windows: PowerShell or cmd)
ssh -L 5930:127.0.0.1:5930 user@server
remote-viewer spice://127.0.0.1:5930    # virt-viewer; on Windows from virt-manager.org
```
`--vnc 1` does the same with VNC on port 5901, for any VNC viewer. The port only
listens on the server's loopback, so it is reachable through the tunnel only.

**On Windows 11 with WSL 2**: WSL runs Linux with nested virtualization and shows its
windows on the Windows desktop, so the QEMU commands above work there. In Ubuntu on WSL,
check that `/dev/kvm` exists, `sudo apt install qemu-system-x86 qemu-utils ovmf`, add
yourself to the `kvm` group (`sudo usermod -aG kvm $USER`, then `wsl --shutdown` in
PowerShell), and start the VM with `--software` (WSLg's window has no OpenGL for QEMU).

**Prefer a window to a command?** GNOME Boxes and Virtual Machine Manager (virt-manager)
open the ISO directly: choose "Debian 13" as the operating system, give it 4 GB of memory
and 2 or more CPUs. VirtualBox and VMware work too (enable EFI for UEFI); Aurora includes
their guest tools.

### Try it on Hyper-V (Windows)

Step-by-step instructions, including how to let Aurora AI use your PC's graphics card, are in
**[HYPERV.md](HYPERV.md)**: creating a Generation 2 VM (a script does it from the ISO's path),
installing, running AI models on the GPU from Windows, experimental GPU partitioning, and
switching the VM to a newer ISO.

### 2. Write it to a USB stick (4 GB or more)
- **Any OS:** [balenaEtcher](https://etcher.balena.io/), Fedora Media Writer, or Ventoy
  (copy the ISO onto a Ventoy stick).
- **Linux, from a terminal** (replace `sdX` with your stick, and check twice, because this
  erases it):
  ```sh
  sudo dd if=aurora-os-VERSION-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
  ```

### 3. Boot from the stick
Restart and open the boot menu (usually <kbd>F12</kbd>, <kbd>F10</kbd>, <kbd>F9</kbd>,
<kbd>Esc</kbd> or <kbd>Del</kbd>). Pick the USB stick. Both BIOS and UEFI are supported.

> **Secure Boot:** the live USB's boot loader is not signed yet, so disable Secure Boot in
> your firmware settings to start it. See [Known limitations](#known-limitations-and-roadmap).

### 4. Try or install
The Aurora boot menu offers:

| Entry | What it does |
|---|---|
| **Try Aurora OS** | Starts the live desktop. Nothing is written to your disk. |
| **Install Aurora OS** | Starts the live system and opens the installer right away. |
| **Try Aurora OS (safe graphics)** | For graphics cards that show a black screen. |
| **Language · Lingua · Sprache · Idioma** | Starts the live system in one of 20 languages, with the matching keyboard layout. |
| **Boot from hard disk** | Skips the USB stick. |

The live desktop works like Ubuntu's "Try": use it as much as you like, nothing is written to the disk. To install, double-click **Install Aurora OS** on the desktop (or use its icon in the dock). If the installer is already open, this brings it forward; after you close it, it opens again.

### 5. Install, step by step
1. **Welcome**: choose the installer language and check the requirements (20 GB disk,
   2 GB RAM, power plugged in).
2. **Location**: click your region on the map; time zone and formats follow.
3. **Keyboard**: pick the layout and try it in the test field.
4. **Disk** (what is ready-picked follows your disks: *Erase disk* on empty ones,
   *Install alongside* next to Windows or another system):
   - *Erase disk* for a clean install. Optionally tick **Encrypt system** and choose a
     passphrase, typed at every start. Keep the file system on **btrfs** (the default)
     to get automatic snapshots and rollback from the boot menu.
   - *Install alongside* to keep Windows or another Linux: click the partition to shrink,
     drag the divider to size them. The boot menu then offers both, and Windows' own boot
     files are left alone.
   - *Replace a partition* or *Manual partitioning* for full control.
5. **Users**: your name, user name, password, computer name, and whether to
   **log in automatically**.
6. **Summary**: review, then **Install**. A short slideshow runs while files are copied.
7. **Restart** and remove the USB stick when asked.

### 6. First boot
You land in the Welcome app. Pick light or dark, learn the shortcuts, and go. Open **Dev
Hub** to add your favorite toolchains and **App Center** for everything else (Flathub is
already enabled).

## Using Aurora

### Keyboard shortcuts
| Shortcut | Action |
|---|---|
| <kbd>Super</kbd> (tap) / <kbd>Super</kbd>+<kbd>Space</kbd> | Spotlight search |
| <kbd>Super</kbd>+<kbd>A</kbd> | Spotlight search |
| <kbd>Super</kbd>+<kbd>S</kbd> | Control Center |
| <kbd>Super</kbd>+<kbd>W</kbd> | Overview: all open windows |
| <kbd>Super</kbd>+<kbd>Z</kbd> | Snap Layouts |
| <kbd>Super</kbd>+<kbd>T</kbd> | Keep the window on top |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Esc</kbd> | Task Manager |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | Pin an area of the screen |
| <kbd>Super</kbd>+<kbd>Alt</kbd>+<kbd>R</kbd> | Start or stop screen recording (add <kbd>Shift</kbd> for an area) |
| <kbd>Super</kbd>+<kbd>V</kbd> | Clipboard history |
| <kbd>Super</kbd>+<kbd>.</kbd> | Emoji |
| <kbd>Super</kbd>+<kbd>Enter</kbd>, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd> | Terminal |
| <kbd>Super</kbd>+<kbd>E</kbd> | Files |
| <kbd>Super</kbd>+<kbd>I</kbd> | Settings |
| <kbd>Super</kbd>+<kbd>L</kbd> | Lock screen |
| <kbd>Alt</kbd>+<kbd>Tab</kbd> | Switch windows |
| <kbd>Super</kbd>+<kbd>←</kbd> / <kbd>→</kbd> | Snap window to the left or right half |
| <kbd>Super</kbd>+<kbd>Ctrl</kbd>+<kbd>U</kbd> <kbd>I</kbd> <kbd>J</kbd> <kbd>K</kbd> | Snap window to the top-left, top-right, bottom-left, bottom-right quarter |
| <kbd>Super</kbd>+<kbd>Ctrl</kbd>+<kbd>D</kbd> <kbd>F</kbd> <kbd>G</kbd> | Snap window to the left, center, right third |
| <kbd>Super</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Maximize / restore |
| <kbd>Super</kbd>+<kbd>/</kbd> | All keyboard shortcuts at a glance |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> | Pick a color from the screen (hex code copied) |
| <kbd>Super</kbd>+<kbd>M</kbd> | Minimize |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd> | Aurora Assistant |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd> | Writing Tools for the selected text |
| <kbd>Super</kbd>+<kbd>H</kbd> | Dictation (press again to stop) |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd> | Read the selected text aloud |
| <kbd>Super</kbd>+<kbd>F</kbd> | Fullscreen |
| <kbd>Super</kbd>+<kbd>Q</kbd>, <kbd>Alt</kbd>+<kbd>F4</kbd> | Close window |
| <kbd>Super</kbd>+<kbd>1</kbd>…<kbd>9</kbd> | Go to workspace |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>1</kbd>…<kbd>9</kbd> | Move window to workspace |
| <kbd>Print</kbd> / <kbd>Shift</kbd>+<kbd>Print</kbd> | Screenshot of the screen / of an area (saved to Pictures/Screenshots and copied) |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>T</kbd> | Copy the text in an area of the screen (OCR) |
| <kbd>Space</kbd> (in Files) | Quick Look |
| Media keys | Volume and brightness with an on-screen indicator |

Add your own in **Settings → Keyboard → Shortcuts**.

### Going back in time (system snapshots)
On a btrfs install (the installer's default) Aurora keeps snapshots of the system:
- one called **Fresh install**, taken at the first boot;
- one **before every update** or package install (the last 10 are kept);
- daily and weekly ones (the last 5 and 3).

Snapshots are instant and only take the space of what changes afterwards. They cover the
system, not your files in Home: rolling back never loses your documents.

**If an update breaks something:**
1. Restart. In the boot menu choose **Aurora OS snapshots** (hold <kbd>Shift</kbd> or
   press <kbd>Esc</kbd> during boot if the menu is hidden), then the snapshot from before
   the update.
2. Aurora starts as it was then. Check that everything works.
3. Open **Timeshift** (Settings → Software Updates → Open Timeshift), select the same
   snapshot and click **Restore**. Restart once more: the rollback is permanent.

Take one by hand with **Settings → Software Updates → Take a Snapshot Now**, or turn off
the automatic ones there.

### Aurora AI
Aurora AI is **off until you turn it on** in **Settings → AI**. Then:
1. **Choose where answers come from.**
   - *This computer (private):* download a model (Qwen3 1.7B for any computer, Qwen3 4B or
     Gemma 3 4B with 8 GB of memory, Qwen3 8B with 16 GB). It runs locally, even offline;
     nothing is sent anywhere. The model loads when you ask and unloads after 10 idle
     minutes.
   - *Anthropic Claude* or an *OpenAI-compatible* service (OpenAI, Google Gemini, Mistral,
     OpenRouter, Groq, or Ollama on your computer): paste your API key. **API keys are
     billed per use by the provider, separately from any Claude Pro/Max or ChatGPT Plus
     subscription**, which third-party apps can't use. Settings says so right next to the
     key field. To use a subscription, install **Claude Code** or **Codex** from Dev Hub →
     AI Assistants: they sign in with your plan.
2. **Pick where it helps** (each has its own switch): Spotlight (`? question`), the
   terminal (`ask`, `why`), Writing Tools (<kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>W</kbd>),
   Files ("Summarize", "Ask About This File"), screenshots ("Ask Aurora"), notification
   summaries, dictation (<kbd>Super</kbd>+<kbd>H</kbd>), read aloud
   (<kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>) and search by meaning in Spotlight.
3. **Languages.** It answers in the language you write in, and follows "reply in
   Italian" whatever the system language. You can also fix one language for answers and
   one for dictation (or let it detect), and download a reading voice for any of 19
   languages.

The Assistant is in the dock and in the top bar (✦), and opens with
<kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd>. In the terminal:
```sh
ask "find files bigger than 1 GB in my home"   # suggests a command, runs it if you say y
make 2>&1 | why                                 # explains the error and the fix
```

Right-click an app, recent file or project in Spotlight for quick actions. Apps can be
pinned to the dock or desktop; files can be opened in Files, copied by path or handed to
the Assistant; projects can launch a configured workspace. Settings → System Health →
Guided Diagnostics creates a local report for installation, boot/login or app problems.
The default report excludes raw logs; including them is opt-in, and you can edit the
preview before saving. Nothing is uploaded automatically.

### Sharing
- **Files with nearby devices:** right-click a file in Files → *Send to Nearby Device…*
  (LocalSend, works with Android, iPhone, Windows, macOS and Linux). Settings → Sharing →
  *Let nearby devices find this computer* opens the port for receiving.
- **Your Wi-Fi:** Settings → Network → the QR icon next to the connected network. Point a
  phone's camera at it to join.
- **Your screen:** Settings → Sharing → *Share this screen*. Connect from another computer
  with a VNC app (Remmina, TigerVNC, RealVNC) to the address shown, with the password shown.

### Your phone
Install **KDE Connect** on your Android phone (Play Store or F-Droid) or iPhone (App Store),
then in Aurora open **Settings → Sharing** and switch on **Allow phones to connect**. Pair
from the phone. The phone's notifications show up on the desktop, and you can send files
both ways, share the clipboard, control music and use the phone as a touchpad.

### The developer setup
- The terminal is **Ptyxis** (tabs, profiles, and a menu to open shells inside your
  distrobox/podman containers) with JetBrains Mono. The prompt is
  **starship** (git branch and status, language versions, command duration).
- Aliases: `ll`, `la`, `g` (git), `lg` (lazygit), `dc` (docker compose), `bat`, `fd`.
  <kbd>Ctrl</kbd>+<kbd>R</kbd> searches history with fzf.
- `docker` works for your user right after installing (you are in the `docker` group). The
  daemon starts on first use (socket activation), so it costs nothing at boot.
- `distrobox create -i fedora` gives you a Fedora (or Arch, Ubuntu…) container integrated
  with your desktop, like Fedora's Toolbox.
- `portop` shows what is listening on which port, owned by which service or container, and
  kills it with one key.

## Build it yourself

### Requirements
- Linux host with **Docker** and **make**, about **20 GB** free disk and a network
  connection. The whole build runs inside a Debian container, so the host needs nothing
  else.
- For testing: **QEMU** with KVM, and OVMF for UEFI (`sudo apt install qemu-system-x86 ovmf`).

### Build
```sh
git clone https://github.com/padovanl/auroraOS.git && cd auroraOS
make iso          # → out/aurora-os-<version>-amd64.iso (+ .sha256)
make run          # boot it in a QEMU window (BIOS)
make run-uefi     # boot it in a QEMU window (UEFI)
```
The first build downloads about 1.5 GB of packages and takes 20 to 40 minutes. Later builds
reuse the root filesystem and the apt cache and take a few minutes.

**On Windows with WSL 2**, keep the build's own directories on the Linux filesystem:

```sh
make iso WORKVOL=/var/tmp/aurora-work OUTDIR=/var/tmp/aurora-out
```

With a checkout under `/mnt/c`, `work/` lands on DrvFs, which has no Unix ownership, and
`debootstrap` stops in stage 10 with "Tried to extract package, but tar failed".

### What happens during a build
`make iso` builds the `aurora-os-builder` image from `build/Dockerfile`, then runs
`build/build-inner.sh` in a privileged container. It executes the stages in
`build/stages/` in order:

| Stage | What it does |
|---|---|
| `10-bootstrap` | `debootstrap` creates a minimal Debian trixie root filesystem (skipped if one exists). |
| `20-packages` | Writes apt sources, installs every list in `config/packages/`, Firefox and LibreOffice translations, and generates the locales in `config/locales.list`. |
| `25-extras` | Downloads third-party `.deb`s from `config/extra-debs.list` (portop), verified against the publisher's SHA-256 checksums, and archives from `config/extra-archives.list` (the adw-gtk3 theme, grub-btrfs), pinned by SHA-256. |
| `30-system` | Copies `overlay/` into the image, writes the Aurora identity (`os-release`, `issue`, `lsb-release`), hides upstream installer launchers and enables services. |
| `35-defaults` | Firewall on, automatic security updates, fingerprint for sudo and admin prompts, Flathub, Docker socket activation, shell setup, SSH off. |
| `40-desktop` | Builds Aurora's own packages, `aurora-desktop` (shell, apps, data, translations, generated Wayland bindings and themes) and `aurora-artwork` (wallpapers and sounds), into `out/debs/`, and installs them with apt, plus the Aurora archive key. |
| `50-branding` | Renders the Plymouth animation, the GRUB theme and fonts, and the installer branding. |
| `70-pool` | Downloads the boot loader and encryption packages into an offline apt pool for the installer. |
| `80-finalize` | Sets the boot splash, rebuilds the initramfs and cleans caches, logs and the machine id. |
| `90-iso` | Packs the root filesystem into SquashFS (zstd), writes the offline repository and the GRUB menu, and makes a hybrid BIOS+UEFI ISO with `grub-mkrescue`. |

Rebuild only some stages while iterating: `make stage S="40 80 90"`. Build only the
packages with `make debs`, and publish them to the signed apt repository in `docs/apt/`
with `make repo`.
Start over with `make clean` (keeps the apt cache) or `make distclean`.

### Developing the desktop without building an ISO
`desktop/dev/run-headless.sh [scenario.sh]` starts labwc in a container with the headless
wlroots backend, installs the desktop from your working tree, runs the shell, runs the
optional scenario script and saves a screenshot to `work/dev-out/screen.png`. It takes
seconds instead of minutes.

### Configuration
`config/aurora.conf` holds the name, version, codename, Debian suite and mirrors, live user
and default language. Package sets live in `config/packages/*.list` (one package per line,
`#` comments). Bundled languages are in `config/locales.list`.

## How we built Aurora OS: making a Linux distribution, step by step

This chapter tells the whole story, in the order we did it, so you can build your own
distribution with it. It explains what each piece is, why it is needed, what we wrote
ourselves and what we took from others. You need to know how to use a Linux terminal and
read shell and Python code; everything else is explained here.

### 0. What a "distribution" actually is

The Linux kernel alone can't do anything useful for a person. A distribution is the kernel
plus everything around it, chosen, configured and packaged so that it works together:

| Layer | What it does | In Aurora |
|---|---|---|
| Firmware | Built into the computer. Finds a disk and starts its boot loader. | BIOS (old PCs) or UEFI (every PC since ~2012). We support both. |
| Boot loader | Shows the boot menu, loads the kernel and the initramfs into memory. | GRUB 2 (with Debian's signed shim for Secure Boot). |
| Kernel | Drivers, memory, processes, file systems. | Debian's `linux-image-amd64` (6.12 LTS), plus firmware packages. |
| initramfs | A tiny temporary system in RAM that finds and mounts the real root file system. | `initramfs-tools`, extended by `live-boot` on the USB stick. |
| init | The first process: starts every service. | systemd. |
| Userland | Shell, libraries, core tools, package manager. | Debian 13 "trixie" and apt. |
| Graphics stack | Talks to the GPU and draws windows. | Mesa + Wayfire (labwc fallback). |
| Desktop | Everything the user sees: bar, dock, launcher, settings, apps. | **Written by us** in Python + GTK 4. |
| Installer | Copies the system to a disk and makes it bootable. | Calamares, configured and extended by us. |

Making a distribution means deciding each row, then writing the glue that makes them
behave like one product. Almost nobody writes rows 1 to 7: you build on an existing
distribution's packages. We chose **Debian stable**: huge package archive, security
updates for years, and the tooling (`debootstrap`, `live-boot`, apt) is exactly what a
derivative needs. Ubuntu, Mint and elementary are built the same way.

### 1. The plan

1. **Build a root file system** from Debian packages, inside a container, from scripts, so
   any machine can reproduce it (no hand-made steps).
2. **Customize it**: our packages, configuration files, services, branding.
3. **Turn it into a live ISO**: compress the root file system into one image, add a boot
   loader for BIOS and UEFI, and make a hybrid ISO that works burned to a DVD or written
   to a USB stick.
4. **Make it installable**: an installer that partitions a disk, copies the system and
   installs a boot loader.
5. **Write the desktop**: our own shell and apps.
6. **Test all of it automatically**, including booting and installing in virtual machines.

### 2. The build machine: Docker, stages, and why

Everything runs in a Debian container (`build/Dockerfile`), started by `make`. The host
only needs Docker (and KVM for tests), so the build is the same on every Linux machine.
The container is `--privileged` because building a system needs `mount` and `chroot`.

The build is a list of numbered shell scripts in `build/stages/`, run in order by
`build/build-inner.sh`. Each stage can be re-run on its own (`make stage S="40 90"`), so
changing the desktop doesn't mean downloading Debian again. `build/lib.sh` holds the
shared helpers: `log`, `in_chroot` (run a command inside the new system) and the mounts of
`/proc`, `/sys`, `/dev` and `/run` that programs inside a chroot expect.

Configuration lives in plain files, not in the scripts: `config/aurora.conf` (name,
version, Debian suite, mirrors, live user), `config/packages/*.list` (what to install),
`config/locales.list` (boot menu languages), `config/apps.manifest` (default apps).

### 3. Stage 10: an empty Debian (debootstrap)

```sh
debootstrap --arch=amd64 --variant=minbase trixie /work/rootfs http://deb.debian.org/debian
```

`debootstrap` downloads the essential Debian packages and unpacks them into a directory:
the result is a tiny but complete Debian you can `chroot` into. Everything after this
works *inside* that directory with `chroot /work/rootfs <command>`: apt, systemctl and
dpkg think they are running on the new system.

### 4. Stage 20 and 25: packages

`20-packages.sh` sets up apt sources (main, contrib, non-free, non-free-firmware and the
security archive), answers install-time questions ahead of time with
`debconf-set-selections` (so nothing waits for a keyboard), upgrades, and installs the
lists in `config/packages/`:

- `base.list`: kernel, firmware, systemd, NetworkManager, `live-boot`, Plymouth, audio
  (PipeWire), printing, Bluetooth, file systems.
- `desktop.list`: Wayfire, labwc fallback, greetd, GTK 4, libadwaita, gtk4-layer-shell, fonts, portals and
  the apps we ship.
- `installer.list`: Calamares, GRUB for BIOS (`grub-pc-bin`) and UEFI
  (`grub-efi-amd64-bin`), shim, `efibootmgr`, partitioning tools.

A missing package fails loudly instead of being skipped silently. `locale-gen` builds
the languages we offer. `25-extras.sh` adds software that isn't in Debian (downloaded
releases, pinned by version and checksum), for example grub-btrfs and pkgtui.

### 5. Stage 30 and 35: making it Aurora

This is where a Debian becomes a distribution.

- **The overlay.** `overlay/` mirrors the file system: every file in it is copied over
  the root file system with `rsync` (for example `overlay/etc/calamares/`,
  `overlay/etc/xdg/mimeapps.list`, systemd units, the live setup script). This is the
  simplest way to ship configuration.
- **Identity.** `/etc/os-release`, `/etc/issue`, `lsb-release`: what every program reads
  to know which system it runs on. We keep `ID_LIKE=debian` so Debian software still
  recognizes it.
- **Diversions.** When we must replace a file owned by a Debian package, we use
  `dpkg-divert`: dpkg then puts future package versions of that file aside instead of
  overwriting ours. Editing it in place would be undone by the next update.
- **Hidden and renamed apps** (`config/hidden-apps.list`, `renamed-apps.list`): we copy
  a package's `.desktop` file to `/usr/local/share/applications`, which wins over
  `/usr/share`, and change `Name=` or add `NoDisplay=true` (only in the
  `[Desktop Entry]` group, or app actions like "New Window" get renamed too).
- **Services**: `systemctl enable` NetworkManager, greetd (the login manager), the live
  setup, update checks; `systemctl set-default graphical.target`.
- **Defaults** (`35-defaults.sh`): firewall on (ufw: deny incoming), automatic security
  updates, Flathub, Docker only on demand (socket activation), SSH off.

### 6. Stage 40: our own software, as real Debian packages

Our code isn't copied loose into the image: `build/package-desktop.sh` builds real
`.deb` packages (`aurora-desktop`, `aurora-base`…) and stage 40 installs them with apt.
This matters: installed systems get updates of our own code through apt, from our
repository on GitHub Pages (`docs/apt/`, signed with our key), the same way they get
Debian's. After installing, the stage compiles GSettings schemas and icon caches and
registers `.desktop` files.

### 7. Stage 50: branding

`branding/` holds the logo generator (`logo.py` draws it as SVG, then renders PNG/WebP at
every size), the wallpaper series, sounds, the GRUB theme (background, fonts as `.pf2`,
`theme.txt`), the Plymouth boot splash and the installer slideshow. Generating assets from
code means one change updates every size and every place.

### 8. Stage 70 and 80: offline packages and cleanup

- `70-pool.sh` downloads (without installing) the packages the installer may need on a
  machine without internet: GRUB for the other firmware type, signed shim and GRUB for
  Secure Boot, drivers. They go on the ISO as a small apt repository.
- `80-finalize.sh` sets the Plymouth theme, regenerates the initramfs (so it contains
  `live-boot` and the splash), removes caches, logs and machine-specific files such as
  `/etc/machine-id` and SSH host keys: each installed machine must get its own (systemd
  makes a new machine-id at first boot; sshd makes its keys when it first starts).

### 9. Stage 90: the live ISO, BIOS and UEFI

This is the part most people find mysterious. The ISO contains:

```
/live/vmlinuz               the kernel
/live/initrd.img            the initramfs (with live-boot)
/live/filesystem.squashfs   the whole root file system, compressed (zstd), read-only
/boot/grub/grub.cfg         the boot menu
/boot/grub/themes/aurora/   the menu's look
/.aurora-live               an empty marker file, to find the right disk
/pool/                      offline packages for the installer
```

1. **squashfs.** `mksquashfs` packs the root file system into one compressed, read-only
   file, a fraction of its size (the whole ISO is about 2.3 GB).
2. **grub.cfg.** Written by the stage: entries for Try, Install, safe graphics
   (`aurora.safegraphics nouveau.noaccel=1`: software rendering and labwc, keeping the kernel's display driver; plain `nomodeset` would leave Debian's kernel, which has no `simpledrm`, with only a text console), a submenu with 20 languages (it passes `aurora.lang=` and
   `aurora.kbd=` to the kernel), boot from disk, and UEFI firmware settings. All entries
   boot `/live/vmlinuz` with `boot=live`. Each entry has a `--class` (try, install,
   language…) that the theme turns into an icon; the theme (`branding/grub/theme.txt`,
   images drawn by `branding/render.py`, fonts converted with `grub-mkfont`) places the
   logo, a menu card and the countdown in "percent ± pixels", so it stays centered on
   any screen, and `grub.cfg` picks a BIOS variant with one entry less.
3. **grub-mkrescue** (a wrapper around `xorriso`) produces a **hybrid ISO** with *both*
   boot paths:
   - **BIOS**: the firmware reads the first sector of the disk (the MBR), which holds a
     small GRUB boot image; it loads GRUB's core (El Torito boot image for optical
     media), which reads `grub.cfg`.
   - **UEFI**: the firmware doesn't run boot sectors. It looks for a FAT partition, the
     *EFI System Partition*, and runs `\EFI\BOOT\BOOTX64.EFI` from it. grub-mkrescue
     adds a small FAT image with GRUB built as an EFI program.
   - **USB sticks**: the ISO also carries an MBR partition table (isohybrid), so the same
     file written with `dd` or Etcher boots as a hard disk on both kinds of firmware.

   In `grub.cfg`, `$grub_platform` tells which path we came from (UEFI adds the
   "firmware settings" entry).

### 10. How the live system boots

1. Firmware → GRUB → kernel + initrd, with `boot=live` on the command line.
2. The initramfs runs `live-boot`'s scripts: they search every disk for
   `/live/filesystem.squashfs`, mount it read-only, and put a writable layer in RAM on top
   (**overlayfs**). The result is mounted as `/`: you can install software and save files;
   everything disappears at shutdown.
3. systemd starts. `aurora-live-setup` (`overlay/usr/libexec/`, runs only when
   `boot=live` is on the command line) creates the `aurora` user with no password and
   sudo, applies the language and keyboard chosen in the boot menu, and turns on
   automatic login.
4. greetd starts the session: `aurora-session` → Wayfire (or labwc fallback) → our shell. With `aurora.install`
   on the command line ("Install Aurora OS" in the menu), the installer opens right away;
   otherwise the live desktop shows an **Install Aurora OS** icon, like Ubuntu's "Try".

### 11. The installer: Calamares

We didn't write an installer: Calamares is used by dozens of distributions. We write its
**configuration** and a few **modules**.

- `overlay/etc/calamares/settings.conf` lists the pages (welcome, location, keyboard,
  partitions, users, summary) and the **exec** sequence that does the work: partition →
  mount → `unpackfs` (copies the contents of `filesystem.squashfs` to the new disk) →
  fstab, locale, keyboard, users → our `aurora-finalize` → services → our
  `aurora-secureboot` → bootloader → initramfs.
- `modules/partition.conf`: btrfs by default (for snapshots), a 512 MB EFI partition on
  UEFI, optional encryption.
- `modules/bootloader.conf`: runs `grub-install` for the firmware the machine booted
  with, with `installEFIFallback` (also writes `\EFI\BOOT\BOOTX64.EFI`, because some
  firmware forgets boot entries).
- Our Python modules (`overlay/usr/lib/calamares/modules/`):
  - `aurora-secureboot`: on UEFI, installs Debian's Microsoft-signed **shim** and signed
    GRUB from the offline pool, so the installed system boots with Secure Boot on.
  - `aurora-finalize`: greetd autologin if chosen, removes live-only files, sets up
    Timeshift snapshots on btrfs and the snapshot boot menu.
- Branding: `branding/calamares/` (colors, logo, slideshow in QML, translations).

The installed system is the same image as the live one, minus the live parts: that's why
it works the first time.

### 12. The desktop: what we wrote

Most distributions reuse GNOME or KDE. We wrote our own desktop to control every detail,
about **15,000 lines of Python** (`desktop/aurora/`):

- **Language and toolkit.** Python 3 with PyGObject, GTK 4 and libadwaita: fast to write,
  and the same widgets the GNOME apps use, so everything looks consistent.
- **The compositor** is **Wayfire** in the default session: its `animate` plugin draws
  window transitions that GTK cannot apply to other apps. **labwc** remains selectable at
  login as a lightweight fallback. Aurora renders Wayfire's INI from the same preferences
  that Settings keeps in `~/.config/labwc/rc.xml`.
- **The shell** (`desktop/aurora/shell/`) is one process whose windows become **layer
  surfaces** (the `wlr-layer-shell` protocol, through gtk4-layer-shell): the top bar, dock,
  wallpaper and desktop icons, launcher, notifications, hot corners. Layer surfaces sit
  above or below normal windows and can reserve screen space.
- **Seeing other apps' windows**: GTK can't. The shell opens a second Wayland connection
  (pywayland) and speaks `wlr-foreign-toplevel-management` to list, focus, minimize and
  close windows: that powers the dock's dots and window lists, the overview and the top
  bar's app menu.
- **Services** it talks to, over D-Bus: NetworkManager, UPower, PipeWire/WirePlumber
  (`wpctl`), BlueZ, logind, notifications (we implement the
  `org.freedesktop.Notifications` server).
- **Apps**: Settings, Files, the Assistant, Dev Hub, Game Hub, Welcome, the greeter (the
  login screen, a greetd client), lock screen, Quick Look.
- **The session**: `aurora-session` seeds the compositor settings and starts Wayfire by
  default; its autostart starts the shell and restarts it if it crashes. If Wayfire cannot
  start, the session falls back to labwc. The greeter also offers labwc explicitly.
- **Look**: our GTK stylesheet on top of libadwaita, our icon theme (drawn by
  `branding/icons`), labwc theme, cursor, fonts.
- **Languages**: every string goes through gettext (`_()`); translations live in
  `desktop/po/` (10 languages, generated from `desktop/po/sources/*.json`).

### 13. What we wrote, what we used

| Written by us | Taken as is (configured) |
|---|---|
| Build scripts (Bash, ~2,000 lines) | Debian packages, debootstrap, live-boot |
| Desktop shell and apps (Python, ~15,000 lines) | Wayfire, labwc fallback, GTK 4, libadwaita, gtk4-layer-shell |
| Calamares modules and configuration | Calamares, GRUB, shim |
| Branding generators (logo, icons, sounds) and the wallpaper series | Plymouth, greetd |
| Stylesheets (CSS), labwc config (XML) | PipeWire, NetworkManager, systemd |
| Tests (Python, ~2,400 lines), website generator | QEMU, OVMF (for testing) |

Languages used: **Bash** (build, system scripts), **Python** (desktop, installer modules,
tests, tools), **CSS** (look), **XML** (compositor config), **QML** (installer
slideshow), **YAML** (Calamares), **HTML/JS** (website).

### 14. Testing a distribution

A distribution breaks in ways unit tests can't see, so we test at every level
(details in [Testing](#testing)):

1. **Static and unit tests**: syntax, lint, translations, and pure logic.
2. **Headless desktop**: the shell runs in a nested compositor in Docker.
3. **Image checks**: inspect the built root file system (files, services, names).
4. **Boot tests**: QEMU boots the real ISO with BIOS and with UEFI (OVMF). The QEMU
   **guest agent** inside the image lets the test run commands in the VM and check
   services, the session and every default app.
5. **Interaction tests**: a virtual USB tablet and keyboard click and type like a person;
   the shell reports which windows exist.
6. **Install tests**: QEMU installs onto an empty virtual disk by pressing keys in
   Calamares, then boots the installed disk and checks it.

Always check both firmware types: many bugs appear on only one of them.

### 15. Doing it yourself: the shortest path

1. `debootstrap` a Debian stable into a directory, `chroot` in, install a kernel,
   `live-boot`, `systemd-sysv`, a desktop and `calamares`.
2. Add your files (a `/etc/os-release`, a user-creation script, your config).
3. `mksquashfs` it; copy the kernel and initrd next to it in an ISO folder; write a
   `grub.cfg` with `boot=live`; run `grub-mkrescue`.
4. Boot it in QEMU with and without `-bios OVMF.fd`.
5. Configure Calamares (`settings.conf`, `partition.conf`, `bootloader.conf`) and install
   into a virtual disk.
6. Put it all in scripts, then in a container, then add tests. That's a distribution.
   The rest is taste, and care.


## How it works (architecture)

```
┌───────────────────────────────────────────────────────────────────────┐
│ Apps: Settings · Files · Dev Hub · Welcome · Firefox · LibreOffice …   │  GTK 4 / libadwaita
├───────────────────────────────────────────────────────────────────────┤
│ Aurora Shell (one Python process)                                     │
│  wallpaper · menu bar · dock · Spotlight/Launchpad · notifications ·  │  wlr-layer-shell
│  control center · OSD                    window list ← wlr-foreign-   │  toplevel-management
├───────────────────────────────────────────────────────────────────────┤
│ Wayfire (labwc fallback): compositor, window management, animations   │
│ Xwayland for older X11 apps                                           │
├───────────────────────────────────────────────────────────────────────┤
│ Session services: PipeWire/WirePlumber · xdg-desktop-portal ·         │
│ polkit agent · swayidle/gtklock · gnome-keyring                       │
├───────────────────────────────────────────────────────────────────────┤
│ greetd → Aurora Greeter (login) → aurora-session                      │
├───────────────────────────────────────────────────────────────────────┤
│ System: systemd · NetworkManager · BlueZ · UPower · CUPS · ufw ·      │
│ Docker · Flatpak · apt (Debian 13 "trixie")                           │
├───────────────────────────────────────────────────────────────────────┤
│ Linux 6.12 LTS (Debian) · firmware · Mesa                             │
└───────────────────────────────────────────────────────────────────────┘
```

**Boot.** Firmware → GRUB (`/boot/grub/grub.cfg` on the ISO) → kernel and initramfs
(`live-boot` finds `/live/filesystem.squashfs` on the stick and mounts it read-only under a
RAM overlay) → systemd. `aurora-live-setup.service` creates the `aurora` live user and
applies the language and keyboard from the boot menu (`aurora.lang=`, `aurora.kbd=`). Then
greetd logs that user in.

**Session.** `aurora-session` loads the user's language and keyboard, exports the Wayland
environment and starts Wayfire with Aurora's generated INI. The same autostart script
used by the labwc fallback launches Aurora Shell, the
polkit agent, the idle manager, XDG autostart entries and, on first login, the Welcome app.
If the shell ever exits, it is started again (at most five times a minute), so a crash
never leaves the session without its bar, dock and desktop.

**Shell.** Every piece of desktop chrome is a GTK window turned into a Wayland layer surface
with gtk4-layer-shell. The window list comes from a second, raw Wayland connection
(pywayland) speaking `wlr-foreign-toplevel-management`. Commands such as
`aurora-shell launcher` or `aurora-shell volume up` are forwarded to the running instance
through GApplication, which is how compositor keybindings reach it.

**Settings storage.** Desktop options are GSettings keys (`org.aurora.desktop`, plus the
standard `org.gnome.desktop.*` keys that GTK apps and portals follow). Compositor options are
written to `~/.config/labwc/rc.xml` for the fallback and mirrored to
`~/.config/aurora/wayfire.ini` for the default session. Actions
that need root go through a single audited helper, `/usr/libexec/aurora-admin`, called with
`pkexec` under its own polkit action.

**Install.** Calamares copies the SquashFS to the target disk and configures users, locale,
keyboard and fstab. It installs the right GRUB (BIOS or UEFI, with shim) from the offline
pool on the stick. Aurora's own modules (`aurora-finalize`, `aurora-sources`) set up the
login screen or automatic login, remove live-only files and write the final apt sources.

## Under the hood: every technical choice

<!-- tech:start -->

This section explains every component Aurora is built from: what we use, what else we
considered, and why we picked it. Ubuntu is a baseline to beat, not a template to copy.
When something better than Ubuntu's default exists, is packaged in Debian and is
dependable, Aurora uses it.

**How we decide.** For every component we ask, in this order:

1. Is it **dependable**? It must be maintained, widely used and have a good security
   track record.
2. Is it **in Debian 13**? Then it gets security updates from Debian's security team for
   years, and we don't maintain it ourselves.
3. Is it **native on Wayland**?
4. Is it **the better experience**: faster, simpler, more capable, better looking?
5. Is it **free software** with a license we can ship?

Components that fail the first two checks only come in through Dev Hub (installed from
their official source on request) or, rarely, pinned with a checksum at build time.

### Platform

#### Base distribution: Debian 13 "trixie"
- **Alternatives:** Ubuntu LTS, Fedora, Arch Linux, openSUSE, NixOS, building everything
  from source (Linux From Scratch).
- **Why:** Debian stable is the most conservative and widely trusted base. It has about
  60,000 packages, a dedicated security team and years of support per release. Ubuntu is
  itself derived from Debian, but ships snaps and its own branding, which we would have to
  undo. Fedora and Arch move faster than a "just works" desktop needs. NixOS is powerful
  but alien to most users and tutorials. From-source builds would make us responsible for
  every security fix in thousands of packages.

#### Kernel: Linux 6.12 LTS (Debian's `linux-image-amd64`)
- **Alternatives:** Debian backports (newer kernels), Liquorix, XanMod, a custom build.
- **Why:** it is a long-term-support kernel, signed for Secure Boot, and patched by
  Debian's security team. Performance kernels such as Liquorix and XanMod are unsigned and
  follow a separate release stream. Users who need newer hardware support can install the
  backports kernel with one command (see [Versions](#versions-updates-and-the-kernel)).

#### Init and system management: systemd
- **Alternatives:** OpenRC, runit, s6.
- **Why:** everything else relies on it: logind (seat and power management), user
  sessions, socket activation (Docker starts on demand), timers, zram, journald. Leaving it
  out would mean patching around dozens of packages.

#### Package formats: `.deb` + Flatpak (Flathub enabled)
- **Alternatives:** Snap, AppImage only, Nix.
- **Why:** `.deb` gives the whole Debian archive and vendors' own packages. Flatpak adds
  thousands of desktop apps from Flathub in a sandbox, with the latest versions, without
  touching the system. Snap relies on a single proprietary store backend and loads slowly,
  so Aurora doesn't ship it. AppImages still run if you download them.

#### Firmware and drivers
- **Choice:** Debian's `firmware-linux` (free and non-free firmware), Mesa with Vulkan
  and VA-API, the Intel media driver, and `nvidia-detect` with a one-click install of the
  proprietary NVIDIA driver in Settings.
- **Why:** since Debian 12 non-free firmware is an official part of the archive, so Wi-Fi,
  Bluetooth, GPUs and audio work on real laptops out of the box. NVIDIA's driver is
  offered rather than preinstalled, because it has to match the card and kernel.

### Boot and live system

#### Boot loader: GRUB 2 (+ shim for Secure Boot on installed systems)
- **Alternatives:** systemd-boot, rEFInd, Limine.
- **Why:** GRUB is the only option that boots both legacy BIOS and UEFI from the same
  USB stick. It detects Windows for dual boot (os-prober), and Debian signs it for Secure
  Boot. systemd-boot is UEFI-only.

#### Live system: live-boot + SquashFS (zstd)
- **Alternatives:** casper (Ubuntu), dracut's dmsquash-live (Fedora).
- **Why:** live-boot is Debian's native live stack and is what Debian's own live images use.
  zstd compression keeps the image small while decompressing much faster than xz.

#### ISO mastering: `grub-mkrescue` + xorriso
- **Alternatives:** live-build, isohybrid with syslinux.
- **Why:** it produces one hybrid image that boots from DVD or USB, BIOS or UEFI, with a
  single GRUB configuration and theme.

#### Boot splash: Plymouth (script theme)
- **Alternatives:** no splash, a static image theme.
- **Why:** Plymouth is standard across distributions and handles disk-encryption
  passphrase prompts. Our script theme plays a frame animation (the logo draws itself,
  then shimmers) rendered by our own code. greetd has no built-in Plymouth hand-over like
  GDM's, so a drop-in quits the splash when the login starts.

### Installer and first boot

#### Installer: Calamares (based on Debian's configuration)
- **Alternatives:** Ubuntu's Subiquity/Flutter installer, Fedora's Anaconda,
  debian-installer, writing our own.
- **Why:** Calamares is distribution-independent and used by Debian live, Manjaro, KDE
  neon, Lubuntu and many others. It handles the hard parts well: partitioning with KPMcore
  (erase, alongside, replace, manual), LUKS encryption, BIOS and UEFI boot loaders. Its
  modules are easy to extend in Python. Subiquity and Anaconda are tied to their own
  distributions. Writing our own partitioner would put users' data at risk.
- **Aurora additions:** our own branding and slideshow. `aurora-finalize` sets up the
  login screen or automatic login and removes live-only files. `aurora-sources` writes
  deb822 apt sources with backports. `aurora-secureboot` installs the signed shim and
  GRUB on UEFI. An **offline package pool** on the ISO means installing never needs a
  network.
- **Its look:** Calamares lets a distribution replace its side bar with QML and restyle
  the rest with a Qt style sheet. Ours (`branding/calamares/`) puts the steps across the
  top as dots that fill in (`calamares-sidebar.qml`, "sidebar: qml,top"), keeps the
  classic buttons at the bottom (so Alt+N still moves on, which the install test uses),
  and draws check marks as PNGs, because the image has no Qt SVG plugin. Two things it
  can't reach are worked around: names under the partition bars are painted in black, so
  they sit on a light strip; and Qt's own title bar, drawn inside the window, made dialogs
  too short for their text, so Wayfire draws title bars for Qt apps.
- **Keyboard page with "Detect…":** Calamares' `keyboardq` module with our QML
  (`keyboardq.qml`). Detection asks which letters start the top row, then which character
  is next to L (or on the 3 key…), and selects the layout in the module's own model. It
  works by clicking only: Calamares shows QML pages in a widget that never gets the
  keyboard, which is also why the page has no search or "type here" field.

#### File systems: btrfs by default (ext4 and xfs available); LUKS encryption
- **Alternatives:** ext4 by default (Ubuntu, Debian), XFS (RHEL), ZFS (Ubuntu offered it
  experimentally).
- **Why:** btrfs makes snapshots instant and nearly free (copy-on-write), which is what
  lets Aurora take one before every update and boot into it (see
  [Snapshots](#system-snapshots-timeshift-btrfs-mode--grub-btrfs)). It also compresses
  transparently (`compress=zstd:1`: less disk space and fewer SSD writes, at no noticeable
  cost) and checksums data. Fedora and openSUSE have used it by default for years. ZFS
  can't ship in the kernel because of its license and needs DKMS modules.
- **Layout:** Ubuntu-style subvolumes created by Calamares (`mount.conf`): `@` (the
  system), `@home` (your files, never rolled back), `@cache` and `@log` (so caches and
  logs aren't in snapshots and survive a rollback), and `@swap` for the swap file, because
  btrfs can't snapshot a subvolume that holds an active swap file.
- ext4 and xfs are still in the installer. On them, everything works except automatic
  snapshots (Timeshift can still make rsync copies).

#### System snapshots: Timeshift (btrfs mode) + grub-btrfs
- **Alternatives:** Snapper with `snapper-rollback` (openSUSE's approach), Timeshift's
  rsync mode, ZFS boot environments, image-based OSes with A/B updates (Fedora Silverblue,
  Vanilla OS), no snapshots (Ubuntu).
- **Why:** Timeshift is in Debian, has a clear graphical app for browsing and restoring
  snapshots, and in btrfs mode snapshots take a second. Its layout (`@`, `@home`) is the
  one most tutorials describe. Snapper is more flexible, but rolling back a Debian-style
  layout with it needs extra tooling and has no GUI in Debian. Immutable A/B systems are
  robust, but they change how you install software, and Aurora wants to stay a normal
  Debian system.
- **How it fits together:**
  - the installer's `aurora-finalize` module writes Timeshift's configuration (the btrfs
    device, including the LUKS container when encrypted) and turns the rest on, on btrfs
    only;
  - `aurora-first-snapshot.service` takes a **"Fresh install"** snapshot at the first boot;
  - an apt hook (`/etc/apt/apt.conf.d/80aurora-snapshot` →
    `/usr/libexec/aurora-snapshot apt`) takes a snapshot **before dpkg changes anything**,
    at most one per ten minutes (an upgrade runs dpkg several times), and keeps the last
    10. It skips itself inside the installer's chroot;
  - Timeshift's own schedule keeps 5 daily and 3 weekly snapshots;
  - **grub-btrfs** adds an "Aurora OS snapshots" submenu to GRUB, and its daemon
    (`grub-btrfsd --timeshift-auto`) refreshes it whenever a snapshot appears or goes. It
    isn't packaged in Debian, so the build installs the upstream 4.13 release pinned by
    SHA-256. Its menu script stays disabled on the live system and on non-btrfs installs.
- Timeshift snapshots are writable, so the snapshotted system boots normally from the
  menu. Restoring it for good is one click in Timeshift.

#### Swap: zram (systemd-zram-generator) + optional swap file
- **Alternatives:** swap partition only, zswap, zram-tools.
- **Why:** compressed swap in RAM makes low-memory machines feel much faster and saves
  SSD writes. systemd's generator needs no configuration. Fedora made the same choice.

#### Login: greetd + Aurora Greeter
- **Alternatives:** GDM, SDDM, LightDM, ly.
- **Why:** greetd is a tiny, secure login daemon made for Wayland. The greeter is our own
  GTK 4 app, so the login screen matches the desktop. It talks greetd's simple JSON
  protocol, which the unit tests cover. GDM pulls in GNOME Shell, SDDM is Qt-based, and
  LightDM is X11-oriented.

### Graphics and the compositor

#### Display server: Wayland (Xwayland for older apps)
- **Why:** Wayland is the modern standard. It gives better security (apps can't read each
  other's input or screen), no tearing, proper fractional scaling and mixed-DPI monitors.
  Xwayland runs the few remaining X11 apps transparently.

#### Compositor: Wayfire, with labwc fallback
- **Alternatives:** Mutter (GNOME), KWin (KDE), Sway, Hyprland, labwc, niri, writing
  our own on wlroots.
- **Why:** Wayfire is packaged in Debian 13, supports the Wayland protocols Aurora Shell
  uses, and its `animate` plugin draws opening, closing, minimize and restore transitions
  for applications of any toolkit. The leaner labwc session stays available in the greeter
  and is started automatically if Wayfire cannot launch. Aurora Settings keeps the labwc
  XML as a shared preference source and renders a Wayfire INI on login and after changes.
  - Mutter and KWin come bundled with their own shells.
  - Sway and niri are tiling-first.
  - Hyprland changes quickly and isn't in Debian.
  - labwc is simpler and retains features such as custom third-width snap regions, but
    does not animate application windows.
  - Writing a compositor would take years to reach labwc's robustness.
- **Trade-off:** Wayfire's plugin system and GL renderer are more complex, especially in
  software-rendered virtual machines. Its server-side decorations do not use labwc's Aurora
  theme; GTK apps use their own Aurora-styled client-side header bars. Blur remains off by
  default. Choose “Aurora (labwc fallback)” at login if Wayfire misbehaves.

#### Window decorations
- **Choice:** GTK apps use Aurora's styled client-side header bars. The generated labwc
  server-side theme remains available in the fallback session; Wayfire's non-GTK server-side
  decorations may differ.
- **Why:** preserve Aurora's appearance for its own apps while using compositor-level
  animation across toolkits.

### Aurora's own desktop

#### Language: Python 3 (PyGObject)
- **Alternatives:** C, Vala, Rust (gtk-rs), JavaScript (GJS, AGS/Astal), Qt/QML.
- **Why:** Python makes the desktop small (about 10,000 lines), readable and easy to
  contribute to. Every part is a plain `.py` file you can change and restart. The
  expensive work happens in C libraries (GTK, GLib, wlroots), so Python is not the
  bottleneck. Rust or C would be faster to run but much slower to write and change. JS
  shell frameworks (AGS/Astal) are elegant but not packaged in Debian.

#### Toolkit: GTK 4 + libadwaita
- **Alternatives:** Qt 6/QML, Iced, Flutter, web technology (Electron/Tauri).
- **Why:** GTK 4 is GPU-accelerated and accessible, and it supports Wayland first.
  libadwaita adds modern widgets (adaptive layouts, toasts, dialogs), dark mode and accent
  colors. Most of the preinstalled apps already use it, so the whole system looks like one
  product. Web technology would cost hundreds of megabytes of RAM for a panel.

#### Desktop surfaces: gtk4-layer-shell
- **Why:** it turns ordinary GTK windows into Wayland layer surfaces (panels, docks,
  overlays, the background) through the standard `wlr-layer-shell` protocol.

#### Window list: pywayland + `wlr-foreign-toplevel-management`
- **Why:** GTK can't see other apps' windows. The dock and the menu bar open a second
  Wayland connection with pywayland and use this protocol to list, focus, minimize and
  close windows. Bindings are generated from the protocol XML at build time.
  - *Lesson learned (tests caught it):* keep the registry and every handle referenced,
    or Python's garbage collector frees them.

#### One process, many surfaces
- **Choice:** wallpaper, menu bar, dock, Spotlight/Launchpad, notifications, OSD, tray
  and Control Center all live in **one** `aurora-shell` process. Commands such as
  `aurora-shell launcher` or `aurora-shell volume up` reach it through GApplication's
  single-instance D-Bus mechanism, which is how keybindings talk to it.
- **Why:** one Python interpreter instead of eight saves memory and keeps state (window
  list, settings) in one place.

#### Notifications: Aurora's own server
- **Alternatives:** mako, dunst, SwayNotificationCenter.
- **Why:** our own implementation of the freedesktop spec (actions, markup, urgency,
  replace, history) integrates with the menu bar, the calendar popover and Do Not Disturb.
  Its markup sanitizer is unit-tested. SwayNotificationCenter isn't in Debian.

#### System tray: our own StatusNotifierItem host
- **Why:** modern tray icons (Discord, Slack, Steam, Nextcloud…) use StatusNotifierItem
  and dbusmenu over D-Bus. Aurora provides the watcher and draws items and menus natively.
  - *Lesson learned:* PyGObject's `bus_watch_name` can report spurious "vanished" events,
    so we listen to `NameOwnerChanged` directly.

#### Search: Spotlight-style providers in Python
- **Why:** apps, settings pages (by keywords), recent files, a **safe** calculator (an AST
  walker, never `eval`), commands (`> …`) and web search. They are simple, fast and all
  covered by tests.
- **Conversions** (`aurora/convert.py`): length, mass, volume, time, speed, data (SI and
  binary), area, energy and temperature, offline. Currencies use the **European Central
  Bank's** daily reference rates: a public XML file with no key or account, fetched only
  when you type a currency conversion and cached for 12 hours. Commercial APIs need keys
  and track usage.
- **Emoji** (`:` prefix): the names come from Python's own Unicode database, so there is
  no extra data file to ship or update.
- **Projects**: git repositories up to two levels inside `~/Projects`, `~/src`, `~/code`,
  `~/git`, `~/dev`, `~/work` and similar, with the current branch. Enter opens the project
  in VS Code, VSCodium, Zed or Sublime if installed, otherwise a terminal there.
- **Clipboard history** (`clip:` prefix, <kbd>Super</kbd>+<kbd>V</kbd>): see below.

#### Clipboard history: `wl-paste --watch` + a tiny store
- **Alternatives:** cliphist, clipman, CopyQ, GPaste.
- **Why:** Wayland only shows the clipboard to the focused app, but the
  `wlr-data-control` protocol lets a helper watch it. The shell runs
  `wl-paste --type text --watch aurora-clipboard store`, and `aurora/clipboard.py` keeps the
  last 100 text entries (up to 64 KB each) in `~/.local/share/aurora/clipboard.json`,
  readable only by you. Password managers mark their copies as sensitive and wl-paste
  passes that on, so passwords are never stored. cliphist would work too, but it adds a
  Go binary for what is about 60 lines of Python, and it doesn't skip sensitive entries.
  CopyQ and GPaste bring their own UIs, and ours is Spotlight. Turn it off or clear it in
  Settings → Privacy.

#### Quick Look: GTK widgets per file type
- **Alternatives:** GNOME Sushi (needs Nautilus and GJS), opening the default app.
- **Why:** a small GTK 4 window (`aurora/quicklook.py`) with the right widget for each type:
  - `Gtk.Picture` for images;
  - `Gtk.Video` (GStreamer, `libgtk-4-media-gstreamer`) for video and audio;
  - **Poppler** for the first pages of a PDF;
  - **GtkSourceView 5** for text and code, with syntax highlighting in the light or dark
    scheme;
  - a folder summary, and for anything else a card with its thumbnail and details.
- Files opens it with <kbd>Space</kbd>; arrow keys move the selection in Files and the
  preview follows. `aurora-quicklook FILE…` works from anywhere.

#### Sun position without a location service (`aurora/sun.py`)
- **Alternatives:** GeoClue (Wi-Fi-based location through an online service), asking the
  user for a city, fixed hours.
- **Why:** the dynamic wallpaper, automatic dark style and Night Light only need sunrise
  and sunset. The time zone you picked in the installer already says roughly where you
  are: tzdata's `zone1970.tab` gives coordinates for every zone. The NOAA solar formulas
  then give the sun's elevation within a few minutes. Nothing leaves the computer and
  nothing asks for permission. Unit tests compare against known sunrise and sunset times.

#### Dynamic wallpaper and automatic dark style (`shell/daycycle.py`)
- **Alternatives:** GNOME's XML slideshows (fixed clock times), HEIC dynamic wallpapers
  (macOS).
- **Why:** three series of four pictures of the same landscape (dawn, day, dusk, night) live
  in `branding/wallpapers/SERIES/`; Settings → Appearance picks the series. Once a minute the shell checks the sun's
  elevation: night below −6°, dawn and dusk up to 8°, day above. On a change, the new
  picture fades in over 2.5 seconds. Following the sun rather than the clock means
  winter evenings get dark when it's actually dark. The shell keeps
  `~/.cache/aurora/wallpaper` pointing at the current picture for the lock screen, and the
  login screen computes the same phase. "Auto" dark style flips the system color scheme
  at sunset and sunrise. Choosing Dark Style by hand in the Control Center turns Auto off.

#### Overview and hot corners
- **Alternatives:** labwc's built-in window switcher only, a GNOME-style overview with
  live thumbnails.
- **Why:** the overview (`shell/overview.py`) is a full-screen layer with a card per
  window from the foreign-toplevel list, over a blurred screenshot of the desktop (grim at
  half scale, shrunk and scaled back up: a cheap blur with no GPU code). labwc 0.8 doesn't
  let other programs capture single windows yet, so cards show the app icon and title
  instead of live thumbnails. Hot corners (`shell/hotcorners.py`) are 2×2-pixel
  transparent layer surfaces in the corners. The pointer must rest there for 120 ms,
  which avoids triggers on fast passes, and there is a short cooldown afterwards.
- **Quarters and thirds** are labwc snap regions defined in `rc.xml`, so they work with
  keyboard shortcuts and by holding a modifier while dragging.

#### Weather in the calendar: Open-Meteo
- **Alternatives:** libgweather/GNOME Weather's providers (MET Norway), OpenWeatherMap
  (needs an API key).
- **Why:** Open-Meteo is free, open data and needs no key or account. The shell asks
  for the weather at your time zone's main city (never an exact position), at most every
  30 minutes, only when you open the calendar. Fahrenheit is used where it is the local
  convention. Settings → Privacy turns it off.

#### Desktop widgets (`shell/widgets.py`, `shell/devwidgets.py`)
- **Alternatives:** separate layer-shell windows per widget, a web view (as KDE's or
  macOS's widgets are closer to), conky.
- **Why:** each widget is a GTK widget on the wallpaper surface, under the windows, so
  twenty-three of them cost one surface. Positions are saved as fractions of the screen and
  sizes follow its height, so a resolution change keeps the layout. Dragging is handled by
  the desktop surface, not by the widget: a gesture on a moving widget shifts its own
  coordinates at every step and makes it jump. A widget is a small slot that measures
  itself (a `Gtk.Box` can't: its layout manager ignores `measure`), holding the visible
  card. Anything that runs a program (git, podman, nvidia-smi, ss) runs in a thread. In
  Wayfire, floating windows are scaled into the new work area after a resolution change
  through its IPC (`shell/refit.py`); labwc moves them back on screen itself.

#### Session sounds: synthesized, not sampled
- **Alternatives:** freedesktop's sound theme, recorded samples, no sounds (Fedora,
  Debian).
- **Why:** the startup and shutdown sounds are generated by `branding/sounds/generate.py`
  with numpy, like the rest of the artwork. They aim for the warm, organic feel of
  Ubuntu's sounds without copying them. A synthesized **marimba** (modal synthesis of a
  wooden bar: tuned partials at 1 : 3.93 : 9.2 that fade at different rates, plus the
  soft click of the mallet) plays a short motif in D major over a round bass note.
  - Startup rises and resolves on a chord held by a soft felt pad.
  - Shutdown walks back down and fades.
- A short room reverb adds space. There are no samples and no licensing questions, and
  the sounds can be changed by editing code. They play with `pw-play` (PipeWire). The
  shell waits 1.8 s for the shutdown sound before powering off, restarting or logging
  out. Both are on by default and switch off together in Settings → Sound.

### Aurora AI

The goal: an assistant that is **private by default, useful where you already are, and
never in your way**. It is off until you switch it on, nothing is downloaded until you
set up a feature, and every place it appears has its own switch.

#### Runtime: llama.cpp's `llama-server`, downloaded on demand
- **Alternatives:** Ollama, LocalAI, vLLM, a Python stack (transformers/PyTorch).
- **Why:** llama.cpp is the engine under most local AI tools. Its official release
  (build b11149, the Vulkan build) is a 30 MB download that runs on any GPU with Vulkan
  (Intel, AMD, NVIDIA) and falls back to the CPU. It serves an OpenAI-compatible API, so
  local and cloud providers share one client. Ollama wraps the same engine but its Linux
  bundle is over 1 GB (CUDA included), and PyTorch stacks are several GB. None of them is
  in Debian, so Aurora downloads the runtime only when you set it up, **pinned by
  SHA-256** like everything in the AI catalog.
  A download only starts if the disk keeps enough room for the system afterwards (5% of
  the disk, at least 2 GB and at most 10 GB); a full disk mid-download removes the
  partial file. Models live in `~/.local/share/aurora/ai`, outside the system snapshots,
  so a removed model frees its space at once. Settings → AI shows the space used and
  removes each model; the shell warns when any disk gets that full.
- **On demand, not always on:** `aurora/ai/server.py` starts the server on the first
  question, on `127.0.0.1` only, and a small reaper stops it after 10 idle minutes, so a
  model only uses memory while you use it.

#### Models: Qwen3 and Gemma 3 (GGUF, 4-bit)
- **Choice:** Qwen3 1.7B (1.1 GB, any computer), Qwen3 4B and Gemma 3 4B (2.5 GB, 8 GB of
  memory), Qwen3 8B (5 GB, 16 GB of memory), quantized to Q4_K_M.
- **Why:** they are the strongest openly licensed models at these sizes, they are
  multilingual (Qwen3 covers over 100 languages, Italian included), and they follow
  instructions well enough for commands and rewriting. Qwen3's "thinking" mode is turned
  off for speed (`enable_thinking: false`), and any `<think>` text that slips through is
  filtered out of the stream.
- **Tested:** on the build machine, Qwen3 1.7B answers a question in Italian in about 4
  seconds, including loading the model, and turns "find files bigger than 1 GB" into
  `find ~/ -type f -size +1G`.

#### Speech: faster-whisper and Piper, in a private venv
- **Dictation:** faster-whisper (Whisper small or base, CTranslate2, int8 on the CPU).
  `pw-record` captures the microphone, Whisper transcribes (detecting the language unless
  you fix one), and `wtype` types the text into the focused app through Wayland's virtual
  keyboard. Alternatives: whisper.cpp (no Linux release binaries), Vosk (lower accuracy),
  cloud speech (not private).
- **Read aloud:** Piper, natural neural voices, one per language (19 voices in the
  catalog). Alternatives: espeak-ng (robotic), cloud TTS.
- Both are Python packages that aren't in Debian, so `pip` installs pinned versions
  (`faster-whisper==1.2.1`, `piper-tts==1.8.0`) into `~/.local/share/aurora/ai/venv`, away
  from the system Python. A round trip on the build machine: Piper reads an Italian
  sentence, and Whisper writes it back nearly word for word.

#### Search by meaning: EmbeddingGemma + SQLite + numpy
- **Why:** EmbeddingGemma 300M is small (333 MB), multilingual and fast on a CPU. The
  indexer (`aurora-ai index`, a user timer every hour, at idle priority) reads text, code,
  Markdown, PDF (`pdftotext`) and Word/LibreOffice documents in the folders you choose,
  and stores a vector per passage in SQLite. A query is one embedding and a matrix
  product. In a test, "quanto devo pagare di luce" finds the English electricity bill,
  and "where is my train seat" finds an Italian PDF ticket.
- **Alternatives:** Tracker/LocalSearch full-text (not by meaning), vector databases
  (overkill for a desktop).

#### Cloud providers, keys and subscriptions
- **Anthropic Claude** (Messages API) and any **OpenAI-compatible** API, with presets for
  OpenAI, Google Gemini, Mistral, OpenRouter, Groq and a local Ollama. Keys are stored in
  the login keyring with libsecret, never in a file.
- **Subscriptions:** Claude and ChatGPT plans are only for the providers' own apps, so
  Aurora AI doesn't pretend to log in with them. Settings says clearly that **API keys
  are billed per use**, separately from any subscription. Dev Hub installs **Claude Code**
  and **Codex**, which do sign in with a plan.

#### Languages
- The system prompt tells the model to answer in the language of your latest message and
  to follow requests like "reply in Italian". It falls back to the system language, and
  you can fix a language in Settings. Dictation detects the spoken language, and any of
  the 19 reading voices can be downloaded.

#### Where it appears
- Spotlight (`?` and, for longer questions, an "Ask Aurora" result); the Assistant (dock,
  top bar, <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>Space</kbd>); Writing Tools on the
  selection (it pastes the result back with `wl-copy` and a simulated
  <kbd>Ctrl</kbd>+<kbd>V</kbd>); Files; screenshots (the OCR text goes to the Assistant,
  so any model can help, not only vision models); notification summaries; `ask` and `why`
  in bash (a `PROMPT_COMMAND` hook remembers the last command and its exit status; `ask`
  runs nothing without a `y`).

#### The Assistant as a layer surface
- **Alternatives:** an ordinary window kept on top by compositor rules (what it was).
- **Why:** a window takes the keyboard when it opens and can't place itself on Wayland.
  As a gtk4-layer-shell surface (top layer, anchored bottom-right, keyboard "on demand")
  it stays above windows on every workspace and only gets the keyboard when clicked. The
  dock writes how much of the screen's bottom it covers to a file in `$XDG_RUNTIME_DIR`;
  the Assistant watches it and sits just above the dock, or at the bottom when there is
  none. Quick actions read the clipboard with `wl-paste`: GTK only sees the clipboard
  while its window has the keyboard. The model picker lists downloaded models, or what an
  OpenAI-compatible server (Ollama, LM Studio) answers at `/models`.

### Look and feel

- **GTK 4 / libadwaita apps** follow the style and accent through the settings portal.
- **GTK 3 and plain GTK 4 apps** use **adw-gtk3** (libadwaita's look for GTK 3), which
  isn't in Debian. The build downloads its upstream release, pinned by SHA-256, and the
  shell switches it between light and dark and writes the accent color.
- **Qt apps** use **QGnomePlatform** with Adwaita-Qt, so they follow the same settings.
- **Icons:** Aurora's own theme (`Aurora` and `Aurora-Dark`), generated by
  `branding/icons/generate.py`: about 45 app icons (rounded squares with a gradient and a
  white glyph), folders with emblems, drives, and some 150 file types as pages with a
  glyph and a colored label. It inherits **Papirus** for symbolic icons (panel, sidebars,
  buttons) and for apps it doesn't draw, and leaves brand icons (Firefox, LibreOffice,
  Steam, VS Code…) to their apps: those are recognized by their logo.
- **Window buttons:** the round colored buttons always show their symbol (×, −, and two
  arrows to expand or restore) instead of hiding it until hover as on a Mac, softer until
  the pointer is over them. The same design is drawn for labwc's fallback borders, GTK 4
  and GTK 3 apps; Wayfire prefers client-side decorations.
- **The desktop stays dark, the apps follow you:** the top bar, the dock, Spotlight,
  Launchpad, the Control Center and notifications are one dark glass over the wallpaper in
  both styles, as GNOME's shell is. Light and Dark change the apps and the desktop widgets
  (which have a light card of their own). Before, everything the shell drew by hand was dark
  but the parts it drew with libadwaita were not, so choosing Light hung a white Control
  Center off a black top bar.
- **Reduce transparency** (Settings → Accessibility → Seeing) makes every glass surface
  solid in one switch, for anyone who reads better without a picture behind the text.
- **The chrome can take the accent** (Settings → Desktop & Dock → Top Bar → *Tint with the accent color*): the top bar's and the dock's glass is mixed with the accent instead of a neutral dark violet. Together with the wallpaper accent below, the desktop's own furniture follows the picture behind it.
- **The accent can come from the wallpaper** (Settings → Appearance → Style → *Color from
  the background*): `aurora/accent.py` reads the picture on screen at 64×64, gathers its
  pixels into 18 hue buckets weighted by saturation, and takes the heaviest one; the color
  is then pulled into a range that still carries white text (yellows and greens are brought
  down further than blues), so no picture can produce an accent you can't read. It follows
  the dynamic background through the day — blue at noon, rose at dusk — and a picture with
  no real color leaves the chosen accent in place.
- **Glass without a blur:** nothing blurs what is behind a surface — that needs the GPU, and
  Aurora runs on software rendering in virtual machines. So the shell's glass is graded by
  what can end up underneath: the top bar and the dock own their strip of screen and keep
  their frosted look, while the surfaces a window can sit behind — Spotlight, the Control
  Center, notifications, the on-screen indicators — are only just see-through, or the window
  under them reads straight through their text. The Control Center used to show the desktop's
  clock and calendar widgets through its own cards.
- **Animations:** Wayfire's `animate` plugin handles application windows, including
  minimize and restore. The shell adds the small motions a desktop is expected to have
  in 2026 and nothing more: menus and popovers grow from the edge they hang off,
  notifications slide in from the corner, the volume and brightness indicators rise,
  a dock icon bounces while its app starts and gives under a click, tiles and window
  cards lift under the pointer. All of it is CSS, so GTK drops every bit of it when
  animations are turned off. GTK and Files retain their own content transitions
  (`gtk4-animations.css`). The Window animations switch controls both layers.
- **Rendering in virtual machines:** labwc uses wlroots' **pixman** renderer and GTK's
  **cairo** renderer without a GPU. Wayfire 0.9 requires GLES, so Aurora uses Mesa's
  software GL in those VMs with wlroots' software-rendering opt-in and retains labwc
  as a selectable or automatic fallback. On Hyper-V, Wayfire still depends on Mesa's
  GLES support; if it cannot initialize EGL, choose the labwc session at login.
- **Fonts:** Inter for the interface (highly legible on screens), JetBrains Mono for code,
  Noto for every script (CJK, Arabic, Devanagari, emoji) so 20 languages render
  correctly.
- **Artwork is code, except the wallpapers:** the logo, boot animation and GRUB theme are
  generated by `branding/` with cairo and Pillow, so any resolution is possible and
  everything is reproducible. The wallpapers are three painted series of pictures
  (Starfall, Veil, Horizon), kept as PNG files in `branding/wallpapers/`.

### Session services

| Area | Choice | Alternatives considered | Why |
|---|---|---|---|
| Audio | **PipeWire + WirePlumber** (+ rtkit) | PulseAudio, JACK | Low latency, Bluetooth codecs, screen-sharing video, compatible with PulseAudio and JACK apps. rtkit gives it realtime priority. |
| Network | **NetworkManager** (+ connection editor, OpenVPN, OpenConnect, WireGuard) | iwd, ConnMan, systemd-networkd | Handles Wi-Fi, Ethernet, VPNs, hotspots and captive portals, and has a mature API (libnm) our shell uses. iwd as a Wi-Fi backend is faster to connect but less compatible with enterprise Wi-Fi, so it stays optional. |
| Bluetooth | **BlueZ** (D-Bus) + **Blueman** for advanced settings | — | BlueZ is the Linux stack. Our Control Center and Settings talk to it directly. |
| Power | **UPower** + **power-profiles-daemon** + **thermald** | TLP, auto-cpufreq | power-profiles-daemon gives the three modes users understand, is what GNOME and KDE use, and doesn't conflict with firmware. TLP needs tuning and conflicts with it. |
| Idle / lock | **swayidle** + **wlopm** + **gtklock** | swaylock, hyprlock | gtklock shows a clock, date and styled password field (our CSS), unlike swaylock. hyprlock isn't in Debian. |
| Night light | **wlsunset** | gammastep, redshift | Small and Wayland-native. The shell runs it with sunrise and sunset for your time zone's coordinates, manual hours, or the same temperature day and night ("all the time"). |
| Screenshots / recording | **grim**, **slurp**, **wl-clipboard**, **wf-recorder** | GNOME Screenshot, OBS | Standard wlroots tools, fast and scriptable. OBS is one click away in App Center. |
| Screenshot annotation | **swappy** | Satty, Flameshot, Ksnip | A small GTK 3 editor made for grim: arrows, text, highlighter, blur. Satty isn't in Debian. Flameshot and Ksnip are Qt apps with their own capture code that works poorly on wlroots. |
| Text from pictures (OCR) | **Tesseract 5** + language data for all 18 boot-menu scripts | EasyOCR, PaddleOCR, online OCR | Offline, fast, in Debian. The neural-network alternatives need hundreds of MB of Python and models. English plus your language is used for recognition. |
| Phone integration | **KDE Connect** | GSConnect, Valent | Works with Android and iPhone, is in Debian, and shows up in our tray. GSConnect needs GNOME Shell. Valent (GTK) isn't in Debian yet. Its ports (1714–1764) stay closed until you switch it on in Settings → Sharing (a ufw profile plus one `aurora-admin` action). |
| Fingerprint | **fprintd** + our PAM profile | Debian's default (off), Howdy (face) | A pam-auth-update profile (`/usr/share/pam-configs/aurora-fingerprint`) puts `pam_fprintd` in the stack for sudo, pkexec and polkit prompts, but skips it for greetd, gtklock, login and ssh. The login password is still needed at boot (it also unlocks the keyring, as macOS does after a restart), and the lock screen can't get stuck waiting for a finger. |
| Media keys / controls | **playerctl** (MPRIS) | — | Controls any player: browsers, Spotify, Celluloid, Rhythmbox. |
| Portals | **xdg-desktop-portal-gtk** + **-wlr** | -gnome, -kde | GTK file choosers and settings; wlr for screenshots and screen sharing in browsers and video calls. |
| Admin prompts | **mate-polkit** agent | polkit-gnome, lxpolkit, our own | A maintained, small GTK agent that works on Wayland. |
| Keyring | **gnome-keyring** (unlocked by PAM at login) + Seahorse | KeePassXC's secret service | Every app that saves passwords (Wi-Fi, browsers, Git credential helpers) supports it. |
| Removable media | **udisks2 + GVfs**, automounted by the shell | udiskie | Drives mount on insert, with a notification to open or eject. |
| Touchpad gestures | **libinput events** read by the shell | libinput-gestures, fusuma, touchégg | labwc 0.8 has no gestures. The shell reads `libinput debug-events` (the user is in the `input` group) and turns 3- and 4-finger movements into actions. The alternatives aren't in Debian or need extra daemons. Workspace switches press labwc's own shortcut through `wtype`. |
| Nearby sharing | **LocalSend** (pinned official `.deb`) | Warpinator, KDE Connect only, Snapdrop | Works with Android, iPhone, Windows, macOS and Linux with no account, over the local network. Warpinator is Linux-first. Its port (53317) opens only when you switch on "Let nearby devices find this computer". |
| Screen sharing | **wayvnc** (RSA-AES encryption, password) | gnome-remote-desktop (RDP), RustDesk | wayvnc is the wlroots VNC server and is in Debian. gnome-remote-desktop needs GNOME's compositor, and RustDesk relays through servers. Port 5900 opens only while sharing. |
| Battery charge limit | **sysfs `charge_control_end_threshold`** + a boot and resume service | TLP, vendor tools | The kernel's standard interface works on many brands. TLP would conflict with power-profiles-daemon. |
| System Health | **Our own checks** (UDisks2 SMART over D-Bus, apt, fwupd, systemd, nvidia-detect, UPower) | GNOME Disks alone, smartd e-mails | One page with every common problem and its fix, no admin password needed to look. |
| Autostart | **aurora-autostart** (XDG autostart) | dex | labwc doesn't run XDG autostart entries. Our small runner honors OnlyShowIn, NotShowIn, Hidden and TryExec, and is unit-tested. |

### Apps

| Role | Choice | Alternatives considered | Why |
|---|---|---|---|
| Files | **Aurora Files** (our own) | Nautilus, Thunar, Nemo | Matches the desktop exactly and is lightweight. Nautilus pulls in large parts of GNOME and assumes GNOME Shell. |
| Terminal | **Ptyxis** (+ foot for scripted windows) | GNOME Console, Kitty, Alacritty, WezTerm, Ghostty | Tabs, profiles, theme-aware, and **container integration**: it opens shells inside distrobox, toolbox and podman containers. It is GNOME's new terminal and Ubuntu's future default. foot stays for Dev Hub's install windows (tiny and scriptable). |
| Text editor | **GNOME Text Editor** + **neovim** | gedit, Kate | Modern GTK 4, fast. neovim for the terminal. |
| Web | **Firefox ESR** | Chromium, rapid-release Firefox (Mozilla's apt repo) | Debian's security team maintains it, and the ESR stays stable. Chromium and rapid Firefox are available too. |
| Mail | **Geary** (shown as "Mail") | Thunderbird, Evolution, Betterbird, KMail, Mailspring | The closest thing to Apple Mail: conversation threads, fast full-text search, a clean single-window design that follows the system theme, and online accounts (Gmail, Outlook.com, IMAP) set up in a minute. Thunderbird is more powerful (OpenPGP, calendar, add-ons, Exchange via EWS) but heavy and styled on its own, so it doesn't inherit the system theme. It is one command away: `sudo apt install thunderbird` or from Flathub. Evolution is the choice for Exchange servers. |
| Office | **LibreOffice** (Writer, Calc, Impress) | OnlyOffice | Fully free software, packaged by Debian, with translations. |
| PDF | **Papers** | Evince | GNOME 48's GTK 4/libadwaita successor to Evince. |
| Images | **Loupe** | Eye of GNOME, gThumb | Fast, GPU-accelerated, GTK 4. |
| Video | **Celluloid** (mpv) | Showtime, Totem, VLC | mpv plays almost anything with hardware decoding. Showtime is pretty but less capable. |
| Music | **Rhythmbox** | Lollypop, Amberol | A complete music library and podcasts. |
| Store | **GNOME Software** + Flatpak plugin | KDE Discover, our own | Covers apt, Flatpak and firmware (fwupd) updates in one place. |
| Backups / snapshots | **Déjà Dup** / **Timeshift** | Borg/Vorta, Snapper | Déjà Dup for personal files (encrypted, incremental). Timeshift for system snapshots, automatic on btrfs (see [Snapshots](#system-snapshots-timeshift-btrfs-mode--grub-btrfs)). |
| Personal | Calendar, Contacts, Weather, Maps, Clocks, Calculator, Camera (Snapshot), Sound Recorder, Scanner, Remmina, Transmission, Disks, Disk Usage, Logs, Characters, Fonts, Power Statistics, Firmware, games | — | The same everyday set Ubuntu ships (GTK 4 versions wherever they exist), listed in `config/apps.manifest` and tested to launch. GNOME System Monitor stays installed but out of Launchpad: Task Manager covers it. |

### Security and privacy
- **Firewall on by default:** ufw, the simplest way to "deny incoming, allow outgoing"
  with a switch in Settings. firewalld has zones for complex setups, which desktops rarely
  need.
- **Automatic security updates** with unattended-upgrades, like Ubuntu. Fedora and Debian
  don't do this by default.
- **AppArmor** (Debian default) confines services and several apps.
- **Full-disk encryption** (LUKS) and **Secure Boot** on installed UEFI systems.
- **Least privilege:** Settings never runs as root. One audited helper does privileged
  actions through polkit.
- **No telemetry**, no crash uploads, no ads, no account required.
- **Every network request the desktop makes on its own**, all of them optional:
  - weather (Open-Meteo, only the time zone's main city, when you open the calendar);
  - exchange rates (the ECB's public file, only when you type a currency conversion);
  - update checks (Debian's and Aurora's repositories);
  - Aurora AI: nothing while it runs on your computer; model and voice downloads (GitHub,
    Hugging Face, PyPI) only when you set up a feature; your questions go to a cloud
    provider only if you choose one and add its key.
  Everything else (sun position, OCR, clipboard history, emoji, unit conversion) runs
  offline.
- **Fingerprint** only for sudo and admin prompts, never instead of the login password.
- **Phone integration** ports stay closed until you turn it on.
- Third-party downloads at build time (portop, adw-gtk3, grub-btrfs) are **verified by
  checksum**.

### Developer experience
- **Preinstalled:** git (+ lfs, lazygit, delta), build-essential, gdb, cmake, shellcheck,
  Python with pip, venv and pipx, Node.js and npm, Docker (+ compose, buildx) with socket
  activation, Podman, distrobox, neovim, tmux and modern CLI tools (ripgrep, fd, fzf,
  bat, btop, jq, httpie, direnv, tldr), starship, zsh, JetBrains Mono and Fira Code, and
  portop.
- **Why these and not more:** they are what nearly every developer uses in their first
  hour. Anything heavier or more personal (IDEs, language toolchains, cloud CLIs,
  databases) goes through **Dev Hub**. It installs from the official source, so versions
  are always current and don't age with Debian's release, and it shows every command in
  a terminal.
- **Containers two ways:** Docker for compatibility with the ecosystem, and Podman plus
  distrobox for rootless containers and "any distro in a terminal" (like Fedora's
  Toolbox). Ptyxis integrates with both.

### Internationalization
- **gettext** for every Aurora string, including the AI's messages (template in
  `desktop/po/aurora.pot`). Aurora's own apps are fully translated into Italian, Spanish,
  French, German, Portuguese, Russian, Chinese (Simplified), Japanese, Arabic and Hindi,
  with the correct plural forms for each language. Translations are kept as JSON keyed by the English text in
  `desktop/po/sources/` and turned into `.po` files by `tools/po-from-json.py`, which
  rejects any translation whose `{placeholders}` differ from the English, so a typo can't
  crash the app.
- There are 20 locales, with Firefox and LibreOffice language packs and Noto fonts for
  every script. The boot menu sets language and keyboard for the live session, and
  Settings changes them per user.

### Aurora's own packages and repository
- **Choice:** `build/package-desktop.sh` builds two `.deb`s with `dpkg-deb`:
  `aurora-desktop` (everything that changes often, about 160 KB) and `aurora-artwork`
  (wallpapers and sounds, about 20 MB, rarely changes). `tools/publish-apt.sh` makes a
  signed apt repository (`apt-ftparchive`, `InRelease` and `Release.gpg` with an Ed25519
  key) for GitHub Pages.
- **Alternatives:** a Launchpad PPA or OBS (tied to other distributions' infrastructure),
  reprepro, Flatpak for the desktop (a shell can't run sandboxed), no packages (installed
  systems would never get Aurora updates).
- **Why:** a plain static repository needs no server. apt already knows how to verify,
  upgrade and roll back packages, and a snapshot is taken before each upgrade anyway.

### Game Hub
- **Choice:** the Dev Hub window with a games catalog: Steam, Heroic, Bottles and
  ProtonUp-Qt from Flathub (sandboxed, with their own graphics runtimes, always current),
  Lutris, GameMode and MangoHud from Debian, Waydroid from its official repository.
- **Why:** gaming on Linux is great today but setup is scattered. One click each, from the
  sources their developers recommend.

### Build system
- **Choice:** our own staged Bash scripts running `debootstrap` inside a privileged Debian
  container (`build/`).
- **Alternatives:** live-build (Debian), mkosi, debos, Ubuntu's livecd-rootfs.
- **Why:** the stages are short, readable and each does one thing, and they can be re-run
  individually (`make stage S="40 90"`). The container makes builds identical on any
  Linux host. Fixed configuration lives in `config/`: package lists, languages, the app
  manifest, hidden and renamed launchers, third-party packages with checksums. live-build
  and mkosi are capable, but they add a configuration language on top of what are
  ultimately the same steps.

### Testing
- **Static:** syntax and shellcheck, desktop-file-validate, strict schema compilation,
  XML and YAML parsing, manifest consistency.
- **Unit (pytest):** the logic that could silently break: calculator safety, search,
  markup sanitizing, file operations, labwc config editing, GTK CSS management,
  autostart rules, the greetd protocol, tray icons, sunrise and sunset, unit and currency
  conversion, clipboard history (including skipping passwords), OCR language choice,
  weather parsing, the Spotlight providers, the Night Light schedule.
- **Smoke:** a real labwc session on wlroots' **headless backend** in a container. Every
  app and Settings page opens without exceptions, the tray works end to end, Spotlight
  answers conversions, emoji, clipboard and project searches, Quick Look previews code, a
  PDF and a picture, the overview opens with windows in it, and screenshots are saved.
- **Image:** checks the finished root filesystem and ISO (programs, services, themes,
  installer, cleanliness, BIOS and UEFI boot records, offline pool, every manifest app).
- **Boot:** QEMU boots the real ISO through GRUB, with BIOS and with UEFI (OVMF). The
  **QEMU guest agent** inside the image lets the test run checks in the live system and
  launch every default app with the real session environment.
- **Install:** the real installer, driven by key presses sent through QEMU's monitor (no
  test hooks inside the installer), installs onto an empty virtual disk. The installed
  system then boots on its own and is checked: user, login, btrfs layout, snapshots and
  the snapshot boot menu.
- **What the tests have already caught:**
  - a heap-corrupting GRUB font on BIOS;
  - a missing Docker CLI;
  - Plymouth hiding the desktop;
  - games unreachable from the session PATH;
  - two garbage-collection bugs, a Files crash and a Settings crash;
  - a 25-second black desktop: the shell asked D-Bus to start BlueZ on machines with no
    Bluetooth adapter;
  - a theme built for a newer GTK filling logs with CSS errors;
  - the shell passing its `gtk4-layer-shell` preload on to every app it started, which
    crashed GTK 3 apps (Firefox, LibreOffice, Geary) launched from the dock.
  - the installer's "strong password" check failing every password, because the
    cracklib dictionary wasn't installed;
  - installing was impossible: `unsquashfs` (squashfs-tools) was missing from the image,
    so Calamares couldn't copy the system to the disk.

### Bugs we found and how we fixed them
Real bugs met while building Aurora, most of them by using the system the way a person
does (on real hardware, in QEMU and on Hyper-V). Each fix has a test that would catch it
coming back.

| Symptom | Cause | Fix |
|---|---|---|
| On Hyper-V, after installing, the VM skipped the disk and tried the network (PXE). | Boot entries written by the guest into the VM's firmware are unreliable on Hyper-V ([Debian #949751](https://bugs.debian.org/949751)), and the disk's fallback path held shim without the GRUB and config it loads (Debian's signed GRUB always reads `\EFI\debian\grub.cfg`). | The installer uses Debian's `--force-extra-removable` (the full signed chain in `\EFI\debian` and `\EFI\BOOT`, no `fbx64.efi`), writes no firmware entry on Hyper-V and removes the one the bootloader step made. The install test boots the disk with an empty NVRAM, like a fresh Hyper-V VM. |
| Wayfire flickered on Hyper-V. | Hyper-V's display driver copies each frame to the host's video memory when the compositor commits it, right after `glFlush()`, while Mesa's software renderer can still be drawing it in background threads. | On Hyper-V, llvmpipe runs without worker threads (`LP_NUM_THREADS=0`): each frame is complete before it is copied. |
| On Hyper-V, the live ISO didn't start with Secure Boot on (PXE). | The live ISO's boot loader isn't signed. | The Hyper-V script and guide turn Secure Boot off for the ISO; installed systems start GRUB directly there (the signed shim chain on other machines). |
| "Try Aurora OS (safe graphics)" only reached a text login. | It used `nomodeset`, and Debian's kernel has no `simpledrm`: without a KMS driver a Wayland compositor has no display. | Safe graphics keeps the display driver and forces software rendering and labwc (`aurora.safegraphics nouveau.noaccel=1`). |
| "Boot from hard disk" did nothing on UEFI. | It chained to the disk's boot sector, which only BIOS has. | On UEFI it returns to the firmware, which starts the next device. |
| The shell didn't start on Hyper-V. | UPower's display device there isn't a battery, and reading it raised an error. | The battery code reads the device kind; every hardware service fails safe instead of stopping the shell. |
| Double-clicking a file on the desktop did nothing, then took down the whole shell. | `Gtk.FileLauncher` goes through the portal, which can't handle the shell's layer surfaces: a Wayland protocol error. | Files open in their default app directly; the session restarts the shell if it ever exits. |
| Double-clicking a desktop icon never opened it. | The icon button's own gesture claimed the presses, so the second click never arrived. | The double-click gesture runs in the capture phase. |
| Hot corners never fired. | The compositor gives no pointer input to a fully transparent surface. | The corners are 1% opaque: invisible, but they receive the pointer. |
| A top-bar menu opened by shortcut ignored Esc and kept the keyboard. | The menu opened before the bar had keyboard focus, and the bar kept it afterwards. | The bar takes the keyboard first, then opens the menu, and gives it back when it closes. |
| Files' context menu never appeared. | `translate_coordinates()` returns two values in the PyGObject Debian ships, not three. | The call accepts both forms. |
| Text containing "&" vanished in Settings ("Date & Time"), and names like "Tom & Jerry" in Files', Task Manager's and every app's rows and toasts. | Adwaita reads row and toast titles as markup. | Every Aurora app imports `aurora.plaintext`: rows and toasts show plain text, group titles are escaped. |
| The dock stayed magnified, or animated forever under a still pointer. | Resizing icons makes GTK report the pointer again at the same place, which restarted the animation. | Motion at an unchanged position is ignored; magnification is recomputed after the dock rebuilds. |
| The dock's right-click menu listed "Terminal" three times. | Renaming apps at build time also renamed their actions (New Window, Preferences…). | Only the `[Desktop Entry]` group is renamed; an image check guards it. |
| Every installed machine had the same SSH host keys. | `openssh-server` generated them at build time. | The image ships without keys; sshd creates them on each machine. |
| Stale, half-erased regions on screen in virtual machines. | GLES and GTK's GL renderers on Mesa's software rasterizers redraw partially wrong there. | Without a real GPU the compositor uses pixman and GTK uses cairo. |
| GTK 3 apps (Firefox, LibreOffice) crashed when started from the dock. | They inherited the shell's GTK 4 layer-shell preload. | The shell removes the preload before starting apps; the boot test checks it. |
| The boot menu's highlight overlapped the next entry. | GRUB offsets the selected entry's text by its box's border. | The other entries get an invisible box with the same borders. |
| A local AI model could fill the disk. | Downloads didn't check free space. | A download only starts if the disk keeps 5% free (2–10 GB); a full disk mid-download removes the partial file; the shell warns when a disk gets that full. |
| The installer couldn't copy the system, then refused every password. | `squashfs-tools` and the cracklib dictionary were missing from the image. | Both are in the package lists; the install test runs the real installer end to end. |
| The Assistant refused attachments with Ollama or LM Studio on the network. | It only allowed attachments for the built-in local model. | Attachments go to any model on this computer or a private network address, never to a cloud endpoint; a headless test checks both. |
| “Attach file” seemed to do nothing. | The file chooser opened behind the always-on-top Assistant. | labwc and Wayfire keep the portal's file chooser on top too. |
| Wayfire exited at once on virtio-gpu without 3D. | Mesa refuses software rendering when a render node exists, and forcing it crashes Wayfire. | That setup starts labwc; `~/.config/aurora/compositor` can still choose Wayfire. |
| On Hyper-V the installed system sat at “Start PXE over IPv4”. | Not the disk: the VM's boot order had the network before the disk (Hyper-V's default), and our script only moved the DVD first. A report script on the Windows host showed it. | The script and the guide set the whole order: DVD, disk, network. |
| On Hyper-V the installed system still didn't start: “The boot loader did not load an operating system”, whatever boot loader was on the disk. | Not the disk, nor any boot loader: the VM's firmware couldn't read the virtual disk (“Read file error - BlockIo” in a UEFI Shell started from the DVD). On that host it reads a `.vhdx` only through a checkpoint's differencing disk, and our VM script turned checkpoints off. Found by trying: the same disk started in a VM made with Windows' defaults, then eight boots with checkpoints on and off. | The script and the guide leave checkpoints as Windows sets them, and turn them back on for VMs made earlier. Meanwhile the EFI step had been changed twice on wrong guesses; on Hyper-V with Secure Boot off it installs GRUB directly, which is what started on the real host. |
| The installer's checkboxes were flat squares with no tick. | The image has no Qt SVG image plugin, so the SVG marks weren't drawn. | The marks are PNGs rendered at build time. |
| The live system warned “Disk almost full”. | Its root is an overlay in RAM with about 2 GB free. | The warning skips file systems in memory (overlay, tmpfs); a unit test checks it. |
| The weather under the calendar disappeared in the live system. | Its time zone is UTC, which has no city to take the location from. | It asks to choose a city in Weather instead of hiding. |
| An encrypted install stopped at the `grub>` prompt after the passphrase. | Calamares made LUKS2, whose default key derivation (argon2id) GRUB 2.12 can't open; it reads `/boot` from the encrypted root. | LUKS1, which GRUB opens; one passphrase at boot, the initramfs then uses a key inside the volume. |
| Installed next to Windows, every GRUB update put Aurora first in the firmware's boot order again, from a second copy. | GRUB's package scripts install to `\EFI\<distributor>` (`aurora`) with a new boot entry each time, besides the installer's `\EFI\debian`. | Only Aurora's helper installs: the stray copy and its entries are removed, and Windows' `\EFI\BOOT` is left to it. |
| "Erase disk" was ready-picked even next to Windows. | One fixed initial choice for every computer. | The installer looks at the disks first: Erase disk only when they're all empty, Install alongside next to another system. |
| Opening a pipe (FIFO) froze Files for good. | `Gtk.FileLauncher` opens the file to read it, which waits for a writer forever. | Pipes and devices say there's nothing to open; Quick Look, checksums and the AI index skip them too. |
| Typing `factorial(99999999)` in Spotlight froze the whole desktop. | The calculator runs in the shell at every key, with no bound on the size of results. | Results are size-checked before computing (about 1,200 digits at most) and big ones read in scientific notation. |
| After the shell restarted, every copy appeared twice in the clipboard history. | Its helpers (clipboard watchers, night light, gestures, screen sharing, recording) outlived it and were started again. | They're started with `setpriv --pdeathsig`: they end with the shell. |
| Recovery mode only said "the root account is locked". | Aurora has no root password (administrators use sudo). | Rescue and emergency mode open a root shell, as on Ubuntu. |
| A custom shortcut with `#` in its command (a link's #anchor) ran cut short in the Aurora session. | Wayfire's config reader treats an unescaped `#` as a comment. | The command is written with `\#`, checked against wf-config itself. |

### Website
- **Choice:** hand-written HTML, CSS and plain JavaScript in `docs/`, served by GitHub
  Pages, with no framework. `tools/build-site.py` turns this section of the README into
  the site's documentation, one page per chapter (`technical-*.html`, with a chapter list,
  "On this page", previous/next, and an index with a topic search), so the two never
  disagree. It also copies Aurora's real icons from the icon generator for the home page.
- **Motion:** an animated aurora sky with twinkling stars, a 3D hero screenshot that
  straightens as you scroll, marquees of Aurora's icons, counters, a typing terminal and
  glows that follow the pointer. All of it is CSS and a few hundred lines of JavaScript,
  and it plays the same for every visitor, whatever their browser's motion setting.

<!-- tech:end -->

## Versions, updates and the kernel

**What is fixed when an ISO is built.** A build installs the versions of every package
that are current in Debian trixie on that day. The kernel is Debian's `linux-image-amd64`,
which today is Linux **6.12 LTS**. Nothing is pinned by hand. Build again tomorrow and you get
tomorrow's versions.

**What happens after installation.** Installed systems keep following Debian trixie:
- **Security and bug fixes** (including new 6.12.x kernels) arrive automatically.
  `unattended-upgrades` installs security updates in the background, and App Center shows
  the rest. You do not need to publish anything for users to get them.
- **Major versions do not jump** within a Debian release (Python, Node.js and so on stay on
  trixie's versions). That is what makes Debian stable. Developers who need the newest
  toolchains get them through Dev Hub, Flatpak or containers.
- **Newer kernels for brand-new hardware** are available from `trixie-backports`, which the
  installer enables (similar to Ubuntu's HWE kernels):
  `sudo apt install -t trixie-backports linux-image-amd64`.

**When to make a new Aurora release.** Build and publish a new ISO when you want new users
to start from newer packages, or when Aurora itself gains features. Bump `AURORA_VERSION` in
`config/aurora.conf`, run `make iso`, `make test-image` and `make test-boot`, then publish
the ISO and its `.sha256`. When Debian 14 comes out, change `DEBIAN_SUITE` for the next
major release.

**Aurora's own updates.** The desktop ships as two Debian packages, `aurora-desktop` and
`aurora-artwork` (version *release.commit-count*, e.g. `0.1.52`), from a signed apt
repository served by GitHub Pages (`https://padovanl.github.io/auroraOS/apt`). Installed
systems update them like any other package. The apt source ships switched off and
`aurora-repo-check.timer` switches it on once the repository answers, so `apt update`
never fails before it is published. To publish: `make debs && make repo`, commit
`docs/apt/`, push. The signing key lives outside the repository
(`~/.config/aurora-os/archive-gnupg`); its public half is
`config/keys/aurora-archive-keyring.gpg`.

## Testing

| Command | Needs | What it checks |
|---|---|---|
| `make test-static` | Docker | Python and shell syntax, shellcheck, `.desktop` files, GSettings schemas (strict), labwc/polkit XML, installer YAML and module sequence, translations, theme generator, duplicate packages. |
| `make test-unit` | Docker | pytest unit tests (`tests/unit/`): calculator safety, search, notification markup sanitizing, copy/move operations, labwc config editing, GTK stylesheet management, autostart filtering, greetd protocol, sunrise/sunset, conversions, clipboard history, OCR language choice, weather parsing, Spotlight providers, Night Light schedule, verified and resumable downloads, the AI catalog's pins, streaming from an OpenAI-compatible server, the reasoning filter, search by meaning, answer and dictation languages, touchpad gestures, disk health parsing, Wi-Fi QR codes. |
| `make test-smoke` | Docker | Starts the shell in a headless Wayland session, opens every Aurora app and every Settings page, opens Spotlight and Launchpad, tries conversions, emoji, clipboard history and project search, previews code, a PDF and a picture with Quick Look, opens the overview, streams an answer in the Assistant and opens Writing Tools (against a fake AI server), opens Game Hub and the AI and System Health pages, fails on any Python exception, and saves screenshots to `work/smoke-out/smoke/`. |
| `make test` | Docker | All three above. |
| `make test-image` | a built ISO | Every app in `config/apps.manifest` installed, visible and executable; themes; identity, required programs, enabled/disabled services, desktop files, installer branding and modules, no leftovers (policy-rc.d, machine id, live user), BIOS and UEFI boot records, ISO contents, GRUB entries, offline pool. The new features too: the dynamic wallpaper set, session sounds, OCR data, Quick Look previewers, grub-btrfs (installed but off until a btrfs install), the fingerprint PAM scope, the KDE Connect firewall profile, the snapshot hook, and the installer's btrfs layout. |
| `make test-boot` | ISO + QEMU/KVM + OVMF | Boots the ISO **through its real GRUB**, once with BIOS and once with UEFI. Through the QEMU guest agent it checks that the live medium is mounted, that the graphical target is reached with no failed units, and that greetd, the live user, labwc and Aurora Shell are up with no exceptions. It also checks that the network is connected, the firewall is active, the Plymouth theme is set and the installer is present, that the theme loads without CSS errors, and that apps started by the shell don't inherit its GTK 4 preload. It then takes a screenshot and checks that the desktop is visible. Finally it **starts every default app** marked in `config/apps.manifest`, with the real session environment, and checks that each one keeps running. (Transmission is not started: a BitTorrent client joining its network from the test VM would trip company firewalls' P2P alerts.) Logs and screenshots are kept in `work/boot-test/`. |
| `make test-interact` | ISO + QEMU/KVM | **Uses the live desktop like a person**: a USB tablet and QMP move the pointer, click, double-click and type, and the shell reports which windows exist and their state (`aurora-shell windows`). It checks that desktop icons select and clear, that a file and a folder open from the desktop, that Install Aurora OS opens the installer, brings it forward and reopens it after closing, that <kbd>Super</kbd>+<kbd>Return</kbd>, <kbd>Super</kbd>+<kbd>M</kbd> and restore work, that <kbd>Esc</kbd> closes the Control Center and gives the keyboard back, that hot corners fire, that Files' context menu and every Settings page open without errors, that no text is lost to markup, and that the shell comes back by itself after being killed. `--push` tries the checkout's code without rebuilding the ISO. Screenshots are kept in `work/interact-test/`; `tests/interact/serve.py` and `do.py` drive the same VM step by step by hand. |
| `make test-files-shortcuts` | ISO + QEMU/KVM | Drives Files with the documented keyboard shortcuts and stresses focus, rapid duplicate requests and asynchronous trash/undo edges; checks Quick Look, rename, trash, permanent-delete cancellation, full-path copying, navigation, tabs, views, search, chained undo/redo, exceptions and GTK criticals. |
| `make test-install` | ISO + QEMU/KVM + OVMF | **Installs Aurora for real**, once with BIOS and once with UEFI. It boots the ISO with an empty 24 GB disk, starts the installer and drives it with key presses sent through QEMU, just like a person at the keyboard: welcome, location, keyboard, "Erase disk" on btrfs, a user with a strong password, Install. Then it boots the installed disk alone and checks the user, the login screen, the live user and live-only files being gone, the btrfs subvolumes and compression, Timeshift's configuration, the "Fresh install" snapshot, a "Before: apt" snapshot after installing a package, and the snapshots entry in the boot menu. Screenshots of every installer step, and of GRUB's snapshot menu, are kept in `work/install-test/`. |

Run `make test && make iso && make test-image && make test-boot && make test-interact && make test-install` before
every release. The
future GitHub release workflow will run the same targets.

## Customizing

- **Settings → Desktop & Dock**: layout presets and every panel, dock, window and launcher
  option.
- **Settings → Appearance**: light, dark or automatic (sunset/sunrise), accent color,
  background (dynamic or a picture, add your own), icons (Aurora, Papirus or any installed
  theme), pointer and size, animations, window animations, fonts, scaling, anti-aliasing,
  hinting, Night Light and its schedule.
- **Settings → Multitasking**: workspaces, hot corners, window snapping.
- **Settings → Accessibility**: text and pointer size, zoom, screen keyboard, scrollbars,
  screen reader, double-click delay.
- **Dev Hub → Shells & Terminals**: install Zsh, fish or another terminal and switch the
  default shell in one click.
- **Config files** (safe to edit; Settings keeps your changes):
  - `~/.config/labwc/rc.xml`: compositor, keybindings, input devices (see the
    [labwc docs](https://labwc.github.io/labwc-config.5.html));
  - `~/.config/gtk-4.0/gtk.css` and `~/.config/gtk-3.0/gtk.css`: add your own CSS below
    Aurora's header line;
  - `~/.config/foot/foot.ini` (start from `/etc/xdg/foot/foot.ini`): terminal;
  - `~/.config/starship.toml` (start from `/etc/aurora/starship.toml`): prompt;
  - `~/.bashrc`: anything on top of `/etc/aurora/bashrc`.
- **Wallpapers**: drop images in `~/.local/share/backgrounds` or `~/Pictures/Wallpapers`.

## Languages

Aurora's default language is English. The ISO includes 20 languages: English (US, UK),
Italian, German, French, Spanish, Portuguese (Brazil, Portugal), Dutch, Polish, Swedish,
Turkish, Russian, Ukrainian, Chinese (Simplified, Traditional), Japanese, Korean, Arabic and
Hindi. Each comes with its locale, fonts (including CJK and Arabic scripts), and Firefox and
LibreOffice translations.

- **Live:** pick a language in the boot menu.
- **Installed:** Settings → Language & Region (language, formats, keyboard layouts,
  switch layouts with <kbd>Alt</kbd>+<kbd>Shift</kbd>).
- **Chinese, Korean and Japanese input:** Settings → Language & Region → Input Methods turns
  on Pinyin, Hangul or Mozc (Fcitx 5). Suggestions appear next to the cursor, also when typing
  on the on-screen keyboard; <kbd>Ctrl</kbd>+<kbd>Space</kbd> switches. A Chinese, Korean or
  Japanese system gets its input method from the first login. Cloud Pinyin is off, so what you
  type stays on the computer.
- **Aurora's own apps** (shell, Settings, Files, Dev Hub, Game Hub, the Assistant and
  every AI message) are fully translated into English, Italian, Spanish, French, German,
  Portuguese, Russian, Chinese (Simplified), Japanese, Arabic and Hindi. The remaining
  bundled languages (Dutch, Polish, Swedish, Turkish, Ukrainian, Chinese (Traditional),
  Korean) show Aurora's own apps in English for now.
- **Translating Aurora's own apps:** strings use gettext (domain `aurora`). Run
  `make -C desktop pot` to regenerate `desktop/po/aurora.pot`; it includes the apps'
  names and descriptions from their `.desktop` files, merged back per language at install. Add translations to
  `desktop/po/sources/<lang>.json` (English text → translation) and run
  `tools/po-from-json.py <lang>`, or edit a `.po` file directly. They are compiled at
  build time.
- **Adding a bundled language:** add a line to `config/locales.list`.

## Website

`docs/` is the project website (a static page for GitHub Pages: in the repository settings
choose *Deploy from a branch* → `main` → `/docs`). It is aimed at users: what Aurora is,
screenshots, features, download and the install guide.

- Preview it locally: `make site` to rebuild the pages, then `tools/serve-site.py --open`
  (http://127.0.0.1:4173). To open it from another device on your network (a phone,
  another PC), run `tools/serve-site.py --lan`: it prints the address to use, such as
  `http://192.168.1.20:4173/`. If the port is taken it moves to the next free one;
  `--port` picks another.
- Set the repository URL and version once in `docs/assets/site.js` (`REPO`, `VERSION`);
  download buttons point to `<REPO>/releases/latest/download/aurora-os-<VERSION>-amd64.iso`.
- Refresh the screenshots from the real ISO with `make vm-screenshots` (boots it in QEMU
  at 1920×1080 and drives the session through the guest agent), or quickly from the
  headless development session with `make screenshots`.
- After editing the README's "Under the hood" section, run `make site` (the static tests
  fail if you forget).
- **The official documentation** is `docs/manual/`, generated by `tools/build-manual.py`
  (`make manual`) from the pages in `docs/_manual/` (one file per section) and from the
  code itself: keyboard shortcuts from `rc.xml`, every GSettings key from the schema, every
  option of every Settings page, widgets, shell commands, command-line tools, the Dev Hub
  and Game Hub catalogs and the default apps. It has search, an "On this page" index and
  light and dark themes. The static tests fail when it is out of date.

## Repository layout

| Path | Contents |
|---|---|
| `config/` | Build settings (`aurora.conf`), package lists, languages, third-party `.deb`s and archives, offline pool list, default-apps manifest, hidden and renamed launchers. |
| `build/` | Builder container, build stages, QEMU runner. |
| `overlay/` | Files copied verbatim into the image: live setup, installer configuration and modules, polkit policy, shell and terminal defaults. |
| `desktop/aurora/shell/` | Aurora Shell: panel, dock, launcher, search, notifications, control center, OSD, wallpaper, window tracking, system services. |
| `desktop/aurora/settingsapp/` | Settings app, one module per group of pages. |
| `desktop/aurora/files/` | Files app. |
| `desktop/aurora/devhub/` | Dev Hub and Game Hub, and their catalogs (`recipes.py`, `games.py`). |
| `desktop/po/` | Translations (`.po`) and their JSON sources. |
| `desktop/aurora/greeter/` | Login screen and greetd client. |
| `desktop/aurora/ai/` | Aurora AI: the pinned download catalog, verified downloads, local servers, providers, keys, speech, search by meaning, the `aurora-ai` CLI. |
| `desktop/aurora/assistant.py` | Aurora Assistant and Writing Tools. |
| `desktop/aurora/{quicklook,clipboard,convert,ocr,sun,weather,screenshare}.py` | Quick Look, clipboard history, conversions, OCR, sun position, weather, screen sharing. |
| `desktop/aurora/{look,labwcconf,apps,settings,i18n}.py` | Shared helpers. |
| `desktop/bin/`, `desktop/libexec/` | Launchers and the privileged helper. |
| `desktop/data/` | labwc config, stylesheets, window themes (generated), schemas, `.desktop` files, icons. |
| `desktop/protocols/` | Wayland protocol XML (bindings generated at build time). |
| `desktop/dev/` | Headless development and test environment. |
| `branding/` | Logo and boot animation, the three wallpaper series, session sounds, Plymouth, GRUB and installer themes: generated by code, except the wallpaper pictures. |
| `tests/` | Static, unit, smoke, image, boot and install tests. |
| `docs/` | The website (GitHub Pages) and the images used by this README. |
| `tools/` | Developer helpers: site preview and generator, the site's wallpaper images (`site-wallpapers.py`), VM screenshots, the AI catalog generator, the apt repository publisher, the translation builder. |

## Known limitations and roadmap

- **Secure Boot on the live USB.** The ISO's GRUB is built with `grub-mkrescue` and is not
  signed, so Secure Boot must be off to boot the stick. *Planned:* boot the ISO through
  Debian's signed shim and GRUB.
- **Publishing the Aurora repository.** The packages and the signed repository are ready
  (`make debs && make repo`); installed systems switch the source on by themselves as
  soon as it is online on GitHub Pages.
- **Translations of Aurora's own apps.** The system, Firefox and LibreOffice come in 20
  languages. Aurora's own apps are complete in 11 of them; Dutch, Polish, Swedish,
  Turkish, Ukrainian, Traditional Chinese and Korean are next (see
  [Languages](#languages)).
- **Claude or ChatGPT subscriptions inside Aurora AI.** Their terms only allow
  subscriptions in the providers' own apps, so Aurora AI uses API keys (billed per use)
  and Dev Hub installs Claude Code and Codex for subscription users. *Idea:* an Aurora MCP
  server so those assistants can act on the desktop.
- **Overview thumbnails.** labwc 0.8 doesn't let other programs capture single windows,
  so the overview shows app icons and titles. *Planned:* live thumbnails once labwc
  supports the `ext-image-capture-source` protocol.
- **Snapshots need btrfs.** On ext4 or xfs installs there is no automatic snapshot or
  boot-menu rollback (Timeshift can still make rsync copies).
- **Fingerprint** unlocks sudo and admin prompts, not the login or lock screen (on
  purpose, see [Fingerprint](#session-services)).
- **Window blur.** labwc has no background blur, so the panels use translucency instead.
- **RAID creation in the installer.** Calamares can install onto existing RAID/LVM but
  cannot create RAID arrays.
- **Release workflow.** A GitHub Actions workflow that builds, tests and publishes releases.

## License and credits

Aurora OS's own code, configuration and artwork are licensed under the
**GNU General Public License v3.0 or later** (see [LICENSE](LICENSE)). Aurora's artwork is
original and generated by the code in `branding/`. The design is inspired by macOS, but
Aurora uses no Apple assets, fonts or icons.

Aurora stands on the work of the Debian project and of the upstream projects listed in
[Under the hood](#under-the-hood-every-technical-choice). Each keeps its own
license. [portop](https://github.com/padovanl/portop) is MIT-licensed.
