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
8. [Under the hood: every technical choice](#under-the-hood-every-technical-choice)
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
| **Control Center** | Output volume and device, microphone and input device, brightness; Wi-Fi (network list, passwords), Wired, Bluetooth (devices), Power Mode, Night Light, Dark Style, Do Not Disturb, Airplane Mode, Screen Recording; media controls for whatever is playing; battery time, screenshot, settings, lock and power. |
| **Notifications** | Freedesktop-compatible server, popups with actions, history in the calendar popover with Do Not Disturb and Clear. |
| **System tray** | StatusNotifierItem icons (Discord, Slack, Steam, Dropbox, Nextcloud…) in the top bar, with their menus. |
| **Desktop icons** | Files in the Desktop folder appear on the background (top left, or top right). |
| **Windows** | labwc compositor: snapping to halves, 4 to 9 workspaces, window switcher, round colored buttons (or monochrome), server-side and GTK decorations styled alike. |
| **Login** | Graphical greeter on greetd, optional automatic login, lock screen, idle screen-off. |
| **Boot** | Branded GRUB menu and an animated Plymouth splash (the logo draws itself). |
| **One look everywhere** | libadwaita apps, GTK 3 apps (adw-gtk3), plain GTK 4 apps, Qt apps (QGnomePlatform), window decorations and icons all follow the light/dark style and accent color you pick. |

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
- **Everyday** (the same set of apps Ubuntu ships): Firefox, Geary Mail, LibreOffice
  (Writer, Calc, Impress), Calendar, Contacts, Weather, Maps, Clocks, Calculator, Text
  Editor, Image Viewer, Document Viewer (PDF), Music (Rhythmbox), Videos (Celluloid, with
  codecs), Camera, Sound Recorder, Document Scanner, Backups (Déjà Dup), Remote Desktop
  (Remmina), Transmission, Archive Manager, Disks, Disk Usage, System Monitor, Logs,
  Characters, Fonts, Power Statistics, Firmware, Passwords and Keys, App Center (GNOME
  Software with Flatpak).
- The full list, with what the tests check for each app, is in
  [`config/apps.manifest`](config/apps.manifest).
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
- **Additional Drivers** (Settings → Software Updates) detects NVIDIA cards and installs the
  recommended proprietary driver.
- **VPNs:** WireGuard, OpenVPN and OpenConnect through NetworkManager's connection editor
  (Settings → Network → VPN and Advanced).

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
| `25-extras` | Downloads third-party `.deb`s from `config/extra-debs.list` (portop), verified against the publisher's SHA-256 checksums, and archives from `config/extra-archives.list` (the adw-gtk3 theme), pinned by SHA-256. |
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
  (erase, alongside, replace, manual), LUKS2 encryption, BIOS and UEFI boot loaders. Its
  modules are easy to extend in Python. Subiquity and Anaconda are tied to their own
  distributions. Writing our own partitioner would put users' data at risk.
- **Aurora additions:** our own branding and slideshow. `aurora-finalize` sets up the
  login screen or automatic login and removes live-only files. `aurora-sources` writes
  deb822 apt sources with backports. `aurora-secureboot` installs the signed shim and
  GRUB on UEFI. An **offline package pool** on the ISO means installing never needs a
  network.

#### File systems: ext4 by default; btrfs and xfs available; LUKS2 encryption
- **Why:** ext4 is the most proven choice for most users. btrfs is there for people who
  want copy-on-write snapshots, and Timeshift supports both.

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

#### Compositor: labwc
- **Alternatives:** Mutter (GNOME), KWin (KDE), Sway, Hyprland, Wayfire, niri, writing
  our own on wlroots.
- **Why:** we wanted our **own** desktop, so we needed a compositor that manages windows
  well and lets an external shell draw everything else. labwc is a small, stable,
  floating-window compositor on wlroots. It supports the protocols a custom shell needs
  (layer-shell, foreign-toplevel management, output management, idle, screencopy,
  virtual keyboard for tests) and is configured with plain XML. We can generate and edit
  that XML from Settings and apply it live.
  - Mutter and KWin come bundled with their own shells.
  - Sway and niri are tiling-first.
  - Hyprland changes quickly and isn't in Debian.
  - Wayfire (in Debian) has eye candy such as blur and animations, but a more complex
    plugin model.
  - Writing a compositor would take years to reach labwc's robustness.
- **Trade-off:** labwc has no background blur, so Aurora uses translucency instead.
  Wayfire stays on our radar for real blur.

#### Window decorations
- **Choice:** themes generated by `desktop/data/themes/generate.py`: round colored
  buttons or monochrome icons, each in a light and a dark variant, following the desktop
  style. GTK apps' own title bars get matching buttons through CSS.
- **Why:** server-side and client-side title bars look the same, and nothing is copied
  from Apple.

### Aurora's own desktop

#### Language: Python 3 (PyGObject)
- **Alternatives:** C, Vala, Rust (gtk-rs), JavaScript (GJS, AGS/Astal), Qt/QML.
- **Why:** Python makes the desktop small (about 7,000 lines), readable and easy to
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

#### Settings storage: GSettings (dconf) + labwc's XML
- **Why:** GSettings is what GTK, portals and GNOME apps already read, so one switch
  (dark style, accent, fonts) reaches every app. Compositor options live in labwc's
  `rc.xml`, which Settings edits with a small tested helper (`aurora/labwcconf.py`) before
  calling `labwc --reconfigure`.

#### Privileged actions: one helper + polkit
- **Alternatives:** running Settings as root, sudo prompts, a custom D-Bus system daemon.
- **Why:** `/usr/libexec/aurora-admin` accepts only a fixed list of operations (firewall,
  SSH, updates, autologin, users) with validated arguments. `pkexec` runs it under its own
  polkit action, so the password prompt names exactly what is being changed. This is a
  much smaller attack surface than a root GUI.

### Look and feel

- **GTK 4 / libadwaita apps** follow the style and accent through the settings portal.
- **GTK 3 and plain GTK 4 apps** use **adw-gtk3** (libadwaita's look for GTK 3), which
  isn't in Debian. The build downloads its upstream release, pinned by SHA-256, and the
  shell switches it between light and dark and writes the accent color.
- **Qt apps** use **QGnomePlatform** with Adwaita-Qt, so they follow the same settings.
- **Icons:** Papirus. It covers the most apps with a consistent look, switches between
  light and dark with the style, and includes brand icons for developer tools.
- **Fonts:** Inter for the interface (highly legible on screens), JetBrains Mono for code,
  Noto for every script (CJK, Arabic, Devanagari, emoji) so 20 languages render
  correctly.
- **Artwork is code:** the logo, boot animation, wallpapers and GRUB theme are generated
  by `branding/` with cairo, numpy and Pillow. There are no opaque binaries, any
  resolution is possible, and everything is reproducible. Wallpapers are computed per
  pixel with tone mapping and dithering, so they show no banding.

### Session services

| Area | Choice | Alternatives considered | Why |
|---|---|---|---|
| Audio | **PipeWire + WirePlumber** (+ rtkit) | PulseAudio, JACK | Low latency, Bluetooth codecs, screen-sharing video, compatible with PulseAudio and JACK apps. rtkit gives it realtime priority. |
| Network | **NetworkManager** (+ connection editor, OpenVPN, OpenConnect, WireGuard) | iwd, ConnMan, systemd-networkd | Handles Wi-Fi, Ethernet, VPNs, hotspots and captive portals, and has a mature API (libnm) our shell uses. iwd as a Wi-Fi backend is faster to connect but less compatible with enterprise Wi-Fi, so it stays optional. |
| Bluetooth | **BlueZ** (D-Bus) + **Blueman** for advanced settings | — | BlueZ is the Linux stack. Our Control Center and Settings talk to it directly. |
| Power | **UPower** + **power-profiles-daemon** + **thermald** | TLP, auto-cpufreq | power-profiles-daemon gives the three modes users understand, is what GNOME and KDE use, and doesn't conflict with firmware. TLP needs tuning and conflicts with it. |
| Idle / lock | **swayidle** + **wlopm** + **gtklock** | swaylock, hyprlock | gtklock shows a clock, date and styled password field (our CSS), unlike swaylock. hyprlock isn't in Debian. |
| Night light | **wlsunset** | gammastep, redshift | Small and Wayland-native, with no location service needed. |
| Screenshots / recording | **grim**, **slurp**, **wl-clipboard**, **wf-recorder** | GNOME Screenshot, OBS | Standard wlroots tools, fast and scriptable. OBS is one click away in App Center. |
| Media keys / controls | **playerctl** (MPRIS) | — | Controls any player: browsers, Spotify, Celluloid, Rhythmbox. |
| Portals | **xdg-desktop-portal-gtk** + **-wlr** | -gnome, -kde | GTK file choosers and settings; wlr for screenshots and screen sharing in browsers and video calls. |
| Admin prompts | **mate-polkit** agent | polkit-gnome, lxpolkit, our own | A maintained, small GTK agent that works on Wayland. |
| Keyring | **gnome-keyring** (unlocked by PAM at login) + Seahorse | KeePassXC's secret service | Every app that saves passwords (Wi-Fi, browsers, Git credential helpers) supports it. |
| Removable media | **udisks2 + GVfs**, automounted by the shell | udiskie | Drives mount on insert, with a notification to open or eject. |
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
| Backups / snapshots | **Déjà Dup** / **Timeshift** | Borg/Vorta, Snapper | Déjà Dup for personal files (encrypted, incremental). Timeshift for system rollbacks on ext4 and btrfs. Snapper is btrfs-only. |
| Personal | Calendar, Contacts, Weather, Maps, Clocks, Calculator, Camera (Snapshot), Sound Recorder, Scanner, Remmina, Transmission, Disks, Disk Usage, System Monitor, Logs, Characters, Fonts, Power Statistics, Firmware, games | — | The same everyday set Ubuntu ships (GTK 4 versions wherever they exist), listed in `config/apps.manifest` and tested to launch. |

### Security and privacy
- **Firewall on by default:** ufw, the simplest way to "deny incoming, allow outgoing"
  with a switch in Settings. firewalld has zones for complex setups, which desktops rarely
  need.
- **Automatic security updates** with unattended-upgrades, like Ubuntu. Fedora and Debian
  don't do this by default.
- **AppArmor** (Debian default) confines services and several apps.
- **Full-disk encryption** (LUKS2) and **Secure Boot** on installed UEFI systems.
- **Least privilege:** Settings never runs as root. One audited helper does privileged
  actions through polkit.
- **No telemetry**, no crash uploads, no ads, no account required.
- Third-party downloads at build time (portop, adw-gtk3) are **verified by checksum**.

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
- **gettext** for all Aurora strings (template in `desktop/po/aurora.pot`, complete Italian
  translation). There are 20 locales, with Firefox and LibreOffice language
  packs and Noto fonts for every script. The boot menu sets language and keyboard for the
  live session, and Settings changes them per user.

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
  autostart rules, the greetd protocol, tray icons.
- **Smoke:** a real labwc session on wlroots' **headless backend** in a container. Every
  app and Settings page opens without exceptions, the tray works end to end, and
  screenshots are saved.
- **Image:** checks the finished root filesystem and ISO (programs, services, themes,
  installer, cleanliness, BIOS and UEFI boot records, offline pool, every manifest app).
- **Boot:** QEMU boots the real ISO through GRUB, with BIOS and with UEFI (OVMF). The
  **QEMU guest agent** inside the image lets the test run checks in the live system and
  launch every default app with the real session environment.
- **What the tests have already caught:** a heap-corrupting GRUB font on BIOS, a missing
  Docker CLI, Plymouth hiding the desktop, games unreachable from the session PATH, two
  garbage-collection bugs, a Files crash and a Settings crash.

### Website
- **Choice:** hand-written HTML, CSS and a few lines of JavaScript in `docs/`, served by
  GitHub Pages, with no framework or build step. `tools/build-site.py` turns this section
  of the README into the site's technical page, so the two never disagree.

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
| `make test-image` | a built ISO | Every app in `config/apps.manifest` installed, visible and executable; themes; identity, required programs, enabled/disabled services, desktop files, installer branding and modules, no leftovers (policy-rc.d, machine id, live user), BIOS and UEFI boot records, ISO contents, GRUB entries, offline pool. |
| `make test-boot` | ISO + QEMU/KVM + OVMF | Boots the ISO **through its real GRUB**, once with BIOS and once with UEFI. Through the QEMU guest agent it checks that the live medium is mounted, that the graphical target is reached with no failed units, and that greetd, the live user, labwc and Aurora Shell are up with no exceptions. It also checks that the network is connected, the firewall is active, the Plymouth theme is set and the installer is present, then takes a screenshot and checks that the desktop is visible. Finally it **starts every default app** marked in `config/apps.manifest`, with the real session environment, and checks that each one keeps running. Logs and screenshots are kept in `work/boot-test/`. |

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

## Website

`docs/` is the project website (a static page for GitHub Pages: in the repository settings
choose *Deploy from a branch* → `main` → `/docs`). It is aimed at users: what Aurora is,
screenshots, features, download and the install guide.

- Preview it locally: `tools/serve-site.py --open` (then http://127.0.0.1:8000).
- Set the repository URL and version once in `docs/assets/site.js` (`REPO`, `VERSION`);
  download buttons point to `<REPO>/releases/latest/download/aurora-os-<VERSION>-amd64.iso`.
- Refresh the screenshots from the real ISO with `make vm-screenshots` (boots it in QEMU
  at 1920×1080 and drives the session through the guest agent), or quickly from the
  headless development session with `make screenshots`.
- After editing the README's "Under the hood" section, run `make site` (the static tests
  fail if you forget).

## Repository layout

| Path | Contents |
|---|---|
| `config/` | Build settings (`aurora.conf`), package lists, languages, third-party `.deb`s and archives, offline pool list, default-apps manifest, hidden and renamed launchers. |
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
| `docs/` | The website (GitHub Pages) and the images used by this README. |
| `tools/` | Developer helpers (`serve-site.py`). |

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
[Under the hood](#under-the-hood-every-technical-choice). Each keeps its own
license. [portop](https://github.com/padovanl/portop) is MIT-licensed.
