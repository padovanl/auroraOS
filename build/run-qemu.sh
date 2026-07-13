#!/bin/bash
# Boot the ISO in QEMU/KVM. Usage: run-qemu.sh [--uefi] [--headless] image.iso
set -euo pipefail

uefi=0 headless=0
while [ $# -gt 1 ]; do
    case "$1" in
        --uefi) uefi=1 ;;
        --headless) headless=1 ;;
        *) break ;;
    esac
    shift
done
iso="${1:?usage: $0 [--uefi] [--headless] image.iso}"

args=(
    -enable-kvm -machine q35 -cpu host -smp 4 -m 4G
    -cdrom "$iso" -boot d
    -device virtio-vga-gl -display gtk,gl=on
    -device intel-hda -device hda-duplex
    -nic user,model=virtio-net-pci
    -usb -device usb-tablet
)

if [ $uefi = 1 ]; then
    ovmf=/usr/share/OVMF/OVMF_CODE_4M.fd
    [ -f "$ovmf" ] || ovmf=/usr/share/ovmf/OVMF.fd
    args+=(-drive "if=pflash,format=raw,readonly=on,file=$ovmf")
fi

if [ $headless = 1 ]; then
    # Replace the display with a monitor socket usable for screendump.
    for i in "${!args[@]}"; do
        [ "${args[$i]}" = "virtio-vga-gl" ] && args[$i]=virtio-vga
        [ "${args[$i]}" = "gtk,gl=on" ] && args[$i]=none
    done
    args+=(-monitor "unix:${QEMU_MONITOR:-/tmp/aurora-qemu.sock},server,nowait"
           -serial "file:${QEMU_SERIAL:-/tmp/aurora-serial.log}")
fi

exec qemu-system-x86_64 "${args[@]}"
