<div align="center">

<img src="docs/aurora-boot.gif" width="220" alt="Aurora OS boot animation">

# Aurora OS

**A beautiful, developer-ready Linux distribution built on Debian.**

A calm macOS-inspired desktop written from scratch, the tools developers use every day
preinstalled, and the rock-solid Debian 13 base underneath.

</div>

---

## Contents

1. [What Aurora OS is](#what-aurora-os-is)
2. [Why Aurora is different](#why-aurora-is-different)
3. [Features](#features)
4. [Get started (users)](#get-started-users)
5. [Using Aurora](#using-aurora)
6. [Build it yourself](#build-it-yourself)
7. [How it works (architecture)](#how-it-works-architecture)
8. [Tools and frameworks, and why we chose them](#tools-and-frameworks-and-why-we-chose-them)
9. [Versions, updates and the kernel](#versions-updates-and-the-kernel)
10. [Testing](#testing)
11. [Customizing](#customizing)
12. [Languages](#languages)
13. [Repository layout](#repository-layout)
14. [Known limitations and roadmap](#known-limitations-and-roadmap)
15. [License and credits](#license-and-credits)

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

## Why Aurora is different

- **Its own desktop, not a re-skin.** The panel, dock, launcher, notifications, control
  center, settings, file manager, login screen and welcome app are written from scratch for
  Aurora (Python + GTK 4 on Wayland), about 7,000 lines you can read and change.
- **Beautiful by default.** A macOS-inspired layout: a menu bar, a floating dock with
  magnification, Spotlight-style search, a Launchpad grid and round colored window buttons.
  All of it uses our own artwork.
- **Made for developers, but not bloated.** Git, compilers, Python, Node.js, Docker, Podman,
  distrobox, a modern shell and a pretty terminal work out of the box. Heavier toolchains
  (VS Code, Rust, Go, Java, Kubernetes, Terraform, databases) are **one click away in Dev
  Hub**, always installed from their official source at their latest version.
- **Customizable for real.** One click switches between four layout presets (Aurora, Classic,
  Studio, Minimal). Past that, the panel and dock can go at the bottom or on either side, be
  floating or full width, auto-hide or magnify, and you pick icon size, window buttons,
  corner radius, fonts, themes, pointer and accent color.
- **Stable underneath.** Debian's security team, Debian's packages, a 6.12 LTS kernel.
  Nothing experimental where it matters.
- **Features people asked the big distros for**, included by default:
  - Flatpak with Flathub enabled (not only snaps);
  - the firewall on out of the box, with a switch in Settings;
  - automatic security updates;
  - compressed RAM swap (zram);
  - system snapshots (Timeshift);
  - a real per-user "log in automatically" switch;
  - custom keyboard shortcuts in Settings;
  - SSH that you turn on with one switch;
  - a Settings search built into the launcher;
  - no telemetry, no ads in the terminal, no snaps forced on you.
- **Tested before every release.** Unit tests, a headless desktop smoke test, image checks
  and real boots in BIOS and UEFI virtual machines (see [Testing](#testing)).

## Features

### Desktop
| | |
|---|---|
| **Menu bar** | Aurora menu (About, Settings, App Center, Dev Hub, Force Quit, Sleep/Restart/Shut Down, Lock, Log Out), the focused app's name, Spotlight, status icons, clock. |
| **Dock** | Pinned and running apps, running indicators, right-click menus (windows, app actions, keep/remove), Launchpad, Trash with "Empty Trash". Magnification, autohide, bottom/left/right, floating or full-width. |
| **Spotlight** (tap <kbd>Super</kbd>) | One search for apps, settings pages, recent files, a calculator (`12*(3+4)`), commands (`> htop`) and the web. |
| **Launchpad** | Full-screen grid of every app. |
| **Control Center** | Volume, brightness, Wi-Fi (with network list and password entry), dark style, Do Not Disturb, night light, battery, lock and power. |
| **Notifications** | Freedesktop-compatible server, popups with actions, history in the calendar popover, Do Not Disturb. |
| **Windows** | labwc compositor: snapping to halves, 4 to 9 workspaces, window switcher, round colored buttons (or monochrome), server-side and GTK decorations styled alike. |
| **Login** | Graphical greeter on greetd, optional automatic login, lock screen, idle screen-off. |
| **Boot** | Branded GRUB menu and an animated Plymouth splash (the logo draws itself). |

### Apps written for Aurora
- **Settings**: Network, Bluetooth, Displays, Sound, Power, Appearance, Desktop & Dock,
  Multitasking, Notifications, Apps (default and startup apps), Mouse & Touchpad, Keyboard
  (repeat and custom shortcuts), Printers, Accessibility, Privacy & Security (screen lock,
  file history, firewall), Sharing (SSH), Users, Language & Region, Date & Time, Software
  Updates, About.
- **Files**: places and drives, grid and list views, search, hidden files, cut/copy/paste
  with progress, trash with restore, rename, new folder, "Open With", properties, open in
  terminal.
- **Dev Hub**: one-click installers for editors, languages, cloud tools and databases.
- **Welcome**: first-run tour (light or dark, shortcuts, install).

### Preinstalled software
- **Developers:** git, git-lfs, lazygit, delta, build-essential, gdb, cmake, shellcheck,
  Python (pip, venv, pipx), Node.js and npm, Docker (+ compose, buildx), Podman, distrobox,
  neovim, tmux, ripgrep, fd, fzf, bat, btop, jq, httpie, direnv, tldr, starship, zsh,
  JetBrains Mono and Fira Code, and **[portop](https://github.com/padovanl/portop)** (see
  which process holds a port and stop it with one key).
- **Everyday** (the same set of apps Ubuntu ships): Firefox, Thunderbird, LibreOffice
  (Writer, Calc, Impress), Calendar, Contacts, Weather, Maps, Clocks, Calculator, Text
  Editor, Image Viewer, Document Viewer (PDF), Music (Rhythmbox), Videos (Celluloid, with
  codecs), Camera, Sound Recorder, Document Scanner, Backups (Déjà Dup), Remote Desktop
  (Remmina), Transmission, Archive Manager, Disks, Disk Usage, System Monitor, Logs,
  Characters, Fonts, Power Statistics, Firmware, Passwords and Keys, App Center (GNOME
  Software with Flatpak).
- **Anything else** is one click away in App Center, which covers the whole Debian archive
  (tens of thousands of packages) and Flathub. Nothing is installed without you asking.

### Hardware
- Firmware for Intel, AMD, Realtek, Atheros, Broadcom and MediaTek Wi-Fi and Bluetooth,
  GPUs and audio (SOF).
- Mesa with Vulkan and VA-API video acceleration, the Intel media driver, NVIDIA detection.
- Laptops: power profiles, thermald, fingerprint readers, screen rotation, firmware updates
  (fwupd), backlight and battery.
- VMs: QEMU/KVM guest agent and SPICE, VMware tools, Hyper-V daemons.
- Printing (CUPS, driverless IPP) and scanning, Bluetooth manager.

### Installer
The installer is Calamares with Aurora's branding. It walks you through language,
location and time zone (detected automatically), keyboard, disk, user and a summary. For
the disk you can erase it, install alongside another OS, replace a partition, or partition
by hand. It supports LUKS2 encryption and ext4, btrfs or xfs. On the user page you set your
name, user name, password and computer name, and choose **automatic login** or the login
screen. Everything the installer needs is on the USB stick, so it **works offline**.

## Get started (users)

### 1. Get the ISO
Build it (see [Build it yourself](#build-it-yourself)), or download a release when they are
published. Check the download:
```sh
sha256sum -c aurora-os-0.1-amd64.iso.sha256
```

### 2. Write it to a USB stick (4 GB or more)
- **Any OS:** [balenaEtcher](https://etcher.balena.io/), Fedora Media Writer, or Ventoy
  (copy the ISO onto a Ventoy stick).
- **Linux, from a terminal** (replace `sdX` with your stick, and check twice, because this
  erases it):
  ```sh
  sudo dd if=aurora-os-0.1-amd64.iso of=/dev/sdX bs=4M status=progress oflag=sync
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

From the live desktop you can install at any time with **Install Aurora OS** in the dock.

### 5. Install, step by step
1. **Welcome**: choose the installer language and check the requirements (20 GB disk,
   2 GB RAM, power plugged in).
2. **Location**: click your region on the map; time zone and formats follow.
3. **Keyboard**: pick the layout and try it in the test field.
4. **Disk**:
   - *Erase disk* for a clean install. Optionally tick **Encrypt system** and choose a
     passphrase.
   - *Install alongside* to keep Windows or another Linux (drag the divider to size them).
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
| <kbd>Super</kbd>+<kbd>Enter</kbd>, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>T</kbd> | Terminal |
| <kbd>Super</kbd>+<kbd>E</kbd> | Files |
| <kbd>Super</kbd>+<kbd>I</kbd> | Settings |
| <kbd>Super</kbd>+<kbd>L</kbd> | Lock screen |
| <kbd>Alt</kbd>+<kbd>Tab</kbd> | Switch windows |
| <kbd>Super</kbd>+<kbd>←</kbd> / <kbd>→</kbd> | Snap window to the left or right half |
| <kbd>Super</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Maximize / restore |
| <kbd>Super</kbd>+<kbd>H</kbd> | Minimize |
| <kbd>Super</kbd>+<kbd>F</kbd> | Fullscreen |
| <kbd>Super</kbd>+<kbd>Q</kbd>, <kbd>Alt</kbd>+<kbd>F4</kbd> | Close window |
| <kbd>Super</kbd>+<kbd>1</kbd>…<kbd>9</kbd> | Go to workspace |
| <kbd>Super</kbd>+<kbd>Shift</kbd>+<kbd>1</kbd>…<kbd>9</kbd> | Move window to workspace |
| <kbd>Print</kbd> / <kbd>Shift</kbd>+<kbd>Print</kbd> | Screenshot of the screen / of an area (saved to Pictures/Screenshots and copied) |
| Media keys | Volume and brightness with an on-screen indicator |

Add your own in **Settings → Keyboard → Shortcuts**.

### The developer setup
- The terminal is **foot** with the Aurora palette and JetBrains Mono. The prompt is
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
git clone <this repository> aurora-os && cd aurora-os
make iso          # → out/aurora-os-<version>-amd64.iso (+ .sha256)
make run          # boot it in a QEMU window (BIOS)
make run-uefi     # boot it in a QEMU window (UEFI)
```
The first build downloads about 1.5 GB of packages and takes 20 to 40 minutes. Later builds
reuse the root filesystem and the apt cache and take a few minutes.

### What happens during a build
`make iso` builds the `aurora-os-builder` image from `build/Dockerfile`, then runs
`build/build-inner.sh` in a privileged container. It executes the stages in
`build/stages/` in order:

| Stage | What it does |
|---|---|
| `10-bootstrap` | `debootstrap` creates a minimal Debian trixie root filesystem (skipped if one exists). |
| `20-packages` | Writes apt sources, installs every list in `config/packages/`, Firefox and LibreOffice translations, and generates the locales in `config/locales.list`. |
| `25-extras` | Downloads third-party `.deb`s from `config/extra-debs.list` (portop) and verifies them against the publisher's SHA-256 checksums. |
| `30-system` | Copies `overlay/` into the image, writes the Aurora identity (`os-release`, `issue`, `lsb-release`), hides upstream installer launchers and enables services. |
| `35-defaults` | Firewall on, automatic security updates, Flathub, Docker socket activation, shell setup, SSH off. |
| `40-desktop` | `make -C desktop install`: the Aurora desktop, generated Wayland bindings, themes, wallpapers, schemas, icons, translations. |
| `50-branding` | Renders the Plymouth animation, the GRUB theme and fonts, and the installer branding. |
| `70-pool` | Downloads the boot loader and encryption packages into an offline apt pool for the installer. |
| `80-finalize` | Sets the boot splash, rebuilds the initramfs and cleans caches, logs and the machine id. |
| `90-iso` | Packs the root filesystem into SquashFS (zstd), writes the offline repository and the GRUB menu, and makes a hybrid BIOS+UEFI ISO with `grub-mkrescue`. |

Rebuild only some stages while iterating: `make stage S="40 80 90"`.
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

## How it works (architecture)

```
┌───────────────────────────────────────────────────────────────────────┐
│ Apps: Settings · Files · Dev Hub · Welcome · Firefox · LibreOffice …   │  GTK 4 / libadwaita
├───────────────────────────────────────────────────────────────────────┤
│ Aurora Shell (one Python process)                                     │
│  wallpaper · menu bar · dock · Spotlight/Launchpad · notifications ·  │  wlr-layer-shell
│  control center · OSD                    window list ← wlr-foreign-   │  toplevel-management
├───────────────────────────────────────────────────────────────────────┤
│ labwc: Wayland compositor (wlroots), window management, keybindings   │
│ Xwayland for older X11 apps                                           │
├───────────────────────────────────────────────────────────────────────┤
│ Session services: PipeWire/WirePlumber · xdg-desktop-portal ·         │
│ polkit agent · swayidle/swaylock · gnome-keyring                      │
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
environment and starts labwc with `~/.config/labwc`. labwc's `autostart` launches Aurora
Shell, the polkit agent, the idle manager, XDG autostart entries and, on first login, the
Welcome app.

**Shell.** Every piece of desktop chrome is a GTK window turned into a Wayland layer surface
with gtk4-layer-shell. The window list comes from a second, raw Wayland connection
(pywayland) speaking `wlr-foreign-toplevel-management`. Commands such as
`aurora-shell launcher` or `aurora-shell volume up` are forwarded to the running instance
through GApplication, which is how labwc keybindings reach it.

**Settings storage.** Desktop options are GSettings keys (`org.aurora.desktop`, plus the
standard `org.gnome.desktop.*` keys that GTK apps and portals follow). Compositor options are
written to `~/.config/labwc/rc.xml` and applied live with `labwc --reconfigure`. Actions
that need root go through a single audited helper, `/usr/libexec/aurora-admin`, called with
`pkexec` under its own polkit action.

**Install.** Calamares copies the SquashFS to the target disk and configures users, locale,
keyboard and fstab. It installs the right GRUB (BIOS or UEFI, with shim) from the offline
pool on the stick. Aurora's own modules (`aurora-finalize`, `aurora-sources`) set up the
login screen or automatic login, remove live-only files and write the final apt sources.

## Tools and frameworks, and why we chose them

| Area | Tool | Why |
|---|---|---|
| Base | **Debian 13 "trixie"** | Stable, huge archive, long security support, the same path Ubuntu took. |
| Root filesystem | **debootstrap** | Debian's official way to create a minimal system. |
| Live system | **live-boot**, **SquashFS** (zstd) | Proven live-USB machinery; zstd gives a good size/speed trade-off. |
| Boot loader | **GRUB 2**, `grub-mkrescue`, **xorriso** | One ISO that boots on BIOS and UEFI, from DVD or USB. |
| Boot splash | **Plymouth** (script theme) | Standard; our animation is rendered frame by frame. |
| Installer | **Calamares** (+ Debian's settings) | The installer used by many distributions; handles partitioning, encryption and boot loaders on real hardware. |
| Compositor | **labwc** (wlroots) | A small, stable Wayland compositor that supports the protocols a custom shell needs (layer-shell, foreign-toplevel, output management) and is easy to configure. Writing a compositor would add a lot of risk for no visible gain. |
| Desktop toolkit | **GTK 4**, **libadwaita**, **PyGObject** | Modern, accessible, themable widgets; Python keeps the desktop small and easy to contribute to. |
| Desktop surfaces | **gtk4-layer-shell** | Turns GTK windows into panels, docks and overlays on Wayland. |
| Window list | **pywayland** + `wlr-foreign-toplevel-management` | GTK cannot see other apps' windows; this protocol can. |
| Login | **greetd** + our GTK greeter | Minimal, secure login daemon with a simple JSON protocol. |
| Network, power, audio, Bluetooth | **NetworkManager** (libnm), **UPower**, **PipeWire/WirePlumber** (`wpctl`), **BlueZ** (D-Bus) | The standard Linux desktop services; nothing custom to maintain. |
| Idle and lock | **swayidle**, **swaylock**, **wlopm** | Small, reliable Wayland tools. |
| Screenshots | **grim**, **slurp**, **wl-clipboard** | Standard wlroots screenshot tools. |
| Night light | **wlsunset** | Gamma control for wlroots compositors. |
| Admin prompts | **polkit** + **mate-polkit** agent | Asks for your password when an app needs root, without running apps as root. |
| Apps | **GNOME Software** + **Flatpak/Flathub** | A graphical store for both Debian packages and Flathub. |
| Security | **ufw**, **unattended-upgrades** | Firewall and automatic security updates with sane defaults. |
| Recovery | **Timeshift** | System snapshots and rollbacks. |
| Terminal | **foot**, **starship** | Fast Wayland-native terminal; a clear, informative prompt. |
| Containers | **Docker**, **Podman**, **distrobox** | Docker for compatibility, Podman for rootless containers, distrobox for other distributions' userlands. |
| Artwork | **cairo**, **numpy**, **Pillow** | Wallpapers, logo, boot animation and GRUB theme are generated by code (`branding/`): no binary sources, any resolution. |
| Build | **Docker**, **make**, Bash | Reproducible builds on any Linux host. |
| Tests | **pytest**, **QEMU** + guest agent, **xorriso**, headless **labwc** | Every layer tested, from functions to a real boot. |

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

> **Important current limitation:** the Aurora desktop itself is installed as files, not as
> a `.deb` package yet. So installed systems get Debian updates automatically, but **not
> updates to the Aurora desktop**. Fixing this (an Aurora apt repository, see the
> [roadmap](#known-limitations-and-roadmap)) is the next infrastructure step.

## Testing

| Command | Needs | What it checks |
|---|---|---|
| `make test-static` | Docker | Python and shell syntax, shellcheck, `.desktop` files, GSettings schemas (strict), labwc/polkit XML, installer YAML and module sequence, translations, theme generator, duplicate packages. |
| `make test-unit` | Docker | pytest unit tests (`tests/unit/`): calculator safety, search, notification markup sanitizing, copy/move operations, labwc config editing, GTK stylesheet management, autostart filtering, greetd protocol. |
| `make test-smoke` | Docker | Starts the shell in a headless Wayland session, opens every Aurora app and every Settings page, opens Spotlight and Launchpad, fails on any Python exception, and saves screenshots to `work/smoke-out/smoke/`. |
| `make test` | Docker | All three above. |
| `make test-image` | a built ISO | Identity, required programs, enabled/disabled services, desktop files, installer branding and modules, no leftovers (policy-rc.d, machine id, live user), BIOS and UEFI boot records, ISO contents, GRUB entries, offline pool. |
| `make test-boot` | ISO + QEMU/KVM + OVMF | Boots the ISO **through its real GRUB**, once with BIOS and once with UEFI. Through the QEMU guest agent it checks that the live medium is mounted, that the graphical target is reached with no failed units, and that greetd, the live user, labwc and Aurora Shell are up with no exceptions. It also checks that the network is connected, the firewall is active, the Plymouth theme is set and the installer is present, then takes a screenshot and checks that the desktop is visible. Logs and screenshots are kept in `work/boot-test/`. |

Run `make test && make iso && make test-image && make test-boot` before every release. The
future GitHub release workflow will run the same targets.

## Customizing

- **Settings → Desktop & Dock**: layout presets and every panel, dock, window and launcher
  option.
- **Settings → Appearance**: light/dark, accent color, background (add your own), icons,
  pointer and size, animations, fonts, scaling, anti-aliasing, hinting, night light.
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
- **Translating Aurora's own apps:** strings use gettext (domain `aurora`). Run
  `make -C desktop pot` to regenerate `desktop/po/aurora.pot`, then copy it to
  `desktop/po/<lang>.po` and translate it. It is compiled automatically at build time.
- **Adding a bundled language:** add a line to `config/locales.list`.

## Repository layout

| Path | Contents |
|---|---|
| `config/` | Build settings (`aurora.conf`), package lists, languages, third-party `.deb`s, offline pool list. |
| `build/` | Builder container, build stages, QEMU runner. |
| `overlay/` | Files copied verbatim into the image: live setup, installer configuration and modules, polkit policy, shell and terminal defaults. |
| `desktop/aurora/shell/` | Aurora Shell: panel, dock, launcher, search, notifications, control center, OSD, wallpaper, window tracking, system services. |
| `desktop/aurora/settingsapp/` | Settings app, one module per group of pages. |
| `desktop/aurora/files/` | Files app. |
| `desktop/aurora/devhub/` | Dev Hub and its catalog (`recipes.py`). |
| `desktop/aurora/greeter/` | Login screen and greetd client. |
| `desktop/aurora/{look,labwcconf,apps,settings,i18n}.py` | Shared helpers. |
| `desktop/bin/`, `desktop/libexec/` | Launchers and the privileged helper. |
| `desktop/data/` | labwc config, stylesheets, window themes (generated), schemas, `.desktop` files, icons. |
| `desktop/protocols/` | Wayland protocol XML (bindings generated at build time). |
| `desktop/dev/` | Headless development and test environment. |
| `branding/` | Logo and boot animation, wallpapers, Plymouth, GRUB and installer themes: all generated by code. |
| `tests/` | Static, unit, smoke, image and boot tests. |
| `docs/` | Images used by this README. |

## Known limitations and roadmap

- **Secure Boot on the live USB.** The ISO's GRUB is built with `grub-mkrescue` and is not
  signed, so Secure Boot must be off to boot the stick. *Planned:* boot the ISO through
  Debian's signed shim and GRUB.
- **Aurora packages and repository.** The desktop is installed as files. *Planned:* package
  it as `aurora-desktop` / `aurora-settings` `.deb`s and host an Aurora apt repository, so
  installed systems receive desktop updates like any other package.
- **System tray (StatusNotifierItem).** Apps with tray icons (chat clients, cloud sync)
  don't show them yet. *Planned:* a tray area in the menu bar.
- **Translations of Aurora's own apps.** The system, Firefox and LibreOffice are
  translated. Aurora's apps are ready for gettext but still need translators.
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
[Tools and frameworks](#tools-and-frameworks-and-why-we-chose-them). Each keeps its own
license. [portop](https://github.com/padovanl/portop) is MIT-licensed.
