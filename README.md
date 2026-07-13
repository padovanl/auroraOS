# Aurora OS

A Linux desktop operating system built on the Debian 13 (trixie) base, with
its own Wayland desktop environment written in Python and GTK4.

- **Kernel and base system**: Linux + Debian userland (apt-compatible)
- **Compositor**: [labwc](https://labwc.github.io/) (wlroots)
- **Desktop**: *Aurora Shell*: panel, app launcher, notifications,
  quick settings, greeter and settings app, all written from scratch
  (`desktop/`)
- **Languages**: English by default; the boot menu and Settings let you
  switch to 20 bundled languages

## Repository layout

| Path | Contents |
|------|----------|
| `config/` | Build configuration, package lists, bundled languages |
| `build/` | Build container, stage scripts, QEMU runner |
| `overlay/` | Files copied verbatim into the root filesystem |
| `desktop/` | Aurora desktop source (shell, settings, greeter, data, translations) |
| `branding/` | Boot splash and GRUB theme |

## Building

Requirements on the host: `docker`, `make`, and `qemu-system-x86_64` with KVM
for testing. The build itself runs as root inside a privileged Debian trixie
container, so the host needs no other tools.

```sh
make iso        # full build -> out/aurora-os-<version>-amd64.iso
make run        # boot the ISO in QEMU (BIOS)
make run-uefi   # boot the ISO in QEMU (UEFI, needs OVMF)
```

The build runs in stages (`build/stages/NN-*.sh`). The bootstrapped rootfs is
kept in `work/`, so iterating on the desktop only needs the later stages:

```sh
make stage S="30 40 80 90"
```

`make clean` drops the rootfs; `make distclean` also drops the apt cache and
the output ISOs.

## Boot options

| Kernel parameter | Effect |
|------------------|--------|
| `aurora.lang=it_IT.UTF-8` | Session language for the live system |
| `aurora.kbd=it` | Keyboard layout (comma-separated for several, e.g. `us,ru`) |

The GRUB *Language* submenu sets both.
