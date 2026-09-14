#!/bin/bash
# Boot the ISO in QEMU/KVM.
# Usage: run-qemu.sh [--uefi] [--disk FILE] [--software] [--spice PORT | --vnc N | --headless] image.iso
#
#   --uefi        UEFI firmware (with its own NVRAM, kept next to the disk)
#   --disk FILE   a 40 GB virtual disk to install on (created if missing); the
#                 ISO still boots first, pick "Boot from hard disk" or pass
#                 an empty ISO argument ('') to start the installed system
#   --software    a display without 3D, like Hyper-V: Wayfire draws on the CPU
#   --spice PORT  no window: serve the screen with SPICE on 127.0.0.1:PORT
#                 (to watch from another computer through an SSH tunnel)
#   --vnc N       the same with VNC on 127.0.0.1:590N
set -euo pipefail

uefi=0 headless=0 software=0 disk="" remote=()
while [ $# -gt 1 ]; do
    case "$1" in
        --uefi) uefi=1 ;;
        --headless) headless=1 ;;
        --software) software=1 ;;
        --disk) disk=$2; shift ;;
        --spice) remote=(-spice "port=$2,addr=127.0.0.1,disable-ticketing=on"
                         -device virtio-serial -chardev spicevmc,id=vdagent,name=vdagent
                         -device virtserialport,chardev=vdagent,name=com.redhat.spice.0
                         -display none); software=1; shift ;;
        --vnc) remote=(-display "vnc=127.0.0.1:$2"); software=1; shift ;;
        *) break ;;
    esac
    shift
done
iso="${1?usage: $0 [--uefi] [--disk FILE] [--software] [--spice PORT | --vnc N | --headless] image.iso}"

args=(
    -enable-kvm -machine q35 -cpu host -smp 4 -m 4G
    -device intel-hda -device hda-duplex
    -nic user,model=virtio-net-pci
    -usb -device usb-tablet
)
[ -n "$iso" ] && args+=(-drive "media=cdrom,file=$iso,readonly=on")

# 3D through the host GPU (virgl) needs a local window. Without it, the
# standard VGA device is used: no render node, so Wayfire runs on the CPU
# exactly as on Hyper-V.
if [ $software = 1 ] || [ $headless = 1 ]; then
    args+=(-vga std)
else
    args+=(-device virtio-vga-gl -display gtk,gl=on)
fi

if [ -n "$disk" ]; then
    [ -e "$disk" ] || qemu-img create -q -f qcow2 "$disk" 40G
    args+=(-drive "file=$disk,if=virtio,format=qcow2")
fi

if [ $uefi = 1 ]; then
    code=/usr/share/OVMF/OVMF_CODE_4M.fd vars=/usr/share/OVMF/OVMF_VARS_4M.fd
    [ -f "$code" ] || { code=/usr/share/ovmf/OVMF.fd vars=""; }
    args+=(-drive "if=pflash,format=raw,readonly=on,file=$code")
    if [ -n "$disk" ] && [ -n "$vars" ]; then
        # Boot entries written by the installer survive a restart, as on a PC.
        [ -e "$disk.vars" ] || cp "$vars" "$disk.vars"
        args+=(-drive "if=pflash,format=raw,file=$disk.vars")
    fi
fi

args+=(-boot "order=dc")
[ ${#remote[@]} -gt 0 ] && args+=("${remote[@]}")

if [ $headless = 1 ]; then
    args+=(-display none
           -monitor "unix:${QEMU_MONITOR:-/tmp/aurora-qemu.sock},server,nowait"
           -serial "file:${QEMU_SERIAL:-/tmp/aurora-serial.log}")
fi

exec qemu-system-x86_64 "${args[@]}"
