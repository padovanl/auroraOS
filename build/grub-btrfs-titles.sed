# Aurora's patch to grub-btrfs' 41_snapshots-btrfs (build/stages/25-extras.sh):
# inside a snapshot, no title row that starts nothing (it was selected first),
# and kernels named "Aurora OS, Linux 6.12…" instead of "vmlinuz-… & initrd.img-…".
s/^    submenu '\${title_submenu}' { echo }"$/"/
s/menuentry '  "\${k}" & "\${i}" & "\${u}"'/menuentry 'Aurora OS, Linux "${kversion}"'/
s/menuentry '  "\${k}" & "\${i}"'/menuentry 'Aurora OS, Linux "${kversion}"'/
