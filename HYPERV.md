# Aurora OS on Hyper-V (Windows), with your PC's GPU for Aurora AI

This guide runs Aurora OS in a Hyper-V virtual machine on Windows 10/11 Pro, Enterprise or
Education, and lets Aurora AI use your PC's graphics card.

One thing to know first: **Hyper-V never gives a Linux VM your GPU for its screen.** The
desktop is always drawn by Hyper-V's virtual display, which is fine for everyday use. The
GPU can still do the heavy work that matters, running AI models, as described in
[part 3](#3-use-your-gpu-for-aurora-ai).

- [1. Create the virtual machine](#1-create-the-virtual-machine)
- [2. Start, try and install](#2-start-try-and-install)
- [3. Use your GPU for Aurora AI](#3-use-your-gpu-for-aurora-ai)
- [4. Advanced: GPU partitioning inside the VM (experimental)](#4-advanced-gpu-partitioning-inside-the-vm-experimental)
- [5. Use a newer ISO in the same VM](#5-use-a-newer-iso-in-the-same-vm)
- [Troubleshooting](#troubleshooting)

## 1. Create the virtual machine

### Turn on Hyper-V (once)

In PowerShell **as administrator**, then restart Windows:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

### The quick way: a script

[`tools/hyperv/New-AuroraVM.ps1`](tools/hyperv/New-AuroraVM.ps1) does all of section 1
from the ISO's path. Download it (on GitHub, open the file and press "Download raw
file"), then in PowerShell **as administrator**, in the folder where you saved it:

```powershell
powershell -ExecutionPolicy Bypass -File .\New-AuroraVM.ps1 -IsoPath "$env:USERPROFILE\Desktop\aurora-os-0.1-amd64.iso"
```

It creates the VM "Aurora" (Generation 2, 8 GB, 4 processors, 60 GB disk in `C:\VMs`),
turns Secure Boot off, sets the boot order, the resolution and enhanced session, starts it and
opens its window. If "Aurora" already exists it keeps it and its disk, and only fixes
its settings and puts the ISO in its DVD drive: run it again whenever you have a newer
ISO. Options: `-Name`, `-MemoryGB`, `-Processors`, `-DiskGB`, `-Folder`, `-Switch`,
`-Width`, `-Height`, `-NoStart`, and `-Recreate` to delete the VM and its disk and start
over. A disk left over in the folder from an earlier VM with the same name is reused
(with `-Recreate`, replaced by a new empty one).

### Or by hand

Copy `aurora-os-0.1-amd64.iso` to your PC (for example to `C:\VMs\`). In PowerShell as
administrator (change the paths and sizes to your liking):

```powershell
$vm  = "Aurora"
$iso = "C:\VMs\aurora-os-0.1-amd64.iso"
$vhd = "C:\VMs\Aurora.vhdx"

New-VM -Name $vm -Generation 2 -MemoryStartupBytes 8GB -NewVHDPath $vhd -NewVHDSizeBytes 60GB `
       -SwitchName "Default Switch"
Set-VM -Name $vm -ProcessorCount 4 -StaticMemory -CheckpointType Disabled `
       -AutomaticCheckpointsEnabled $false
Add-VMDvdDrive -VMName $vm -Path $iso
# DVD, then the disk, then the network: Hyper-V's own order has the network before
# the disk, and the installed system would wait at "Start PXE over IPv4".
Set-VMFirmware -VMName $vm -EnableSecureBoot Off -BootOrder `
    (Get-VMDvdDrive -VMName $vm), (Get-VMHardDiskDrive -VMName $vm), (Get-VMNetworkAdapter -VMName $vm)
Set-VMVideo -VMName $vm -HorizontalResolution 1920 -VerticalResolution 1080 -ResolutionType Single
Set-VMHost -EnableEnhancedSessionMode $false
```

What these settings do:

| Setting | Why |
|---|---|
| Generation 2 | UEFI firmware, like a modern PC. Aurora supports BIOS too, but Gen 2 is faster and supports Secure Boot. |
| 8 GB of RAM, static | The live system runs from memory, and a local AI model needs a lot. Use at least 4 GB. Dynamic memory confuses the live system. |
| 4 processors | More makes the desktop and installs faster. |
| 60 GB disk | At least 20 GB is needed to install, more to keep snapshots and AI models. |
| Secure Boot **off** | Required for the live ISO, whose boot loader is not signed. |
| 1920×1080 | Hyper-V's default screen is small. Pick your monitor's resolution. |
| Enhanced session off | Enhanced session (RDP) doesn't work with Aurora's Wayland desktop and would show a black window. |

The **Aurora** session uses Wayfire and its window animations, on Hyper-V too.
Hyper-V's display has no 3D, so Wayfire draws with Mesa's software renderer
(llvmpipe). Hyper-V's display driver copies every frame into the video memory the
host shows, at the moment the compositor hands it over; llvmpipe normally finishes
drawing in background threads, so half-drawn frames could reach the screen and
flicker. On Hyper-V Aurora therefore runs llvmpipe without worker threads
(`LP_NUM_THREADS=0`), so each frame is complete before it is copied. No Windows
setting gives the VM 3D acceleration. If Wayfire still misbehaves, run
`echo labwc > ~/.config/aurora/compositor` in Aurora's terminal and log in again
(or pick **Aurora Compatibility** at login); `rm ~/.config/aurora/compositor`
goes back to Wayfire.
After copying a newly built ISO, check its SHA-256 against the adjacent
`.iso.sha256` file so an earlier image is not mistaken for the new build.

You can do the same in **Hyper-V Manager** (New → Virtual Machine): choose Generation 2,
then in Settings → Security untick "Enable Secure Boot", and in View untick "Enhanced
Session".

## 2. Start, try and install

1. Connect to the VM (double-click it in Hyper-V Manager) and press **Start**.
2. The Aurora boot menu appears. **Try Aurora OS** starts the live desktop, where nothing
   is written to the virtual disk. **Install Aurora OS** opens the installer right away.
   Use **Language** to start in another language with its keyboard layout.
3. In the live desktop, double-click **Install Aurora OS** to install onto the virtual disk.
   Choose "Erase disk" (it's the VM's empty disk, not your PC's).
4. When the installer finishes, shut down, then remove the ISO so the VM starts from the
   disk:
   ```powershell
   Set-VMDvdDrive -VMName "Aurora" -Path $null
   ```
   The boot order set above (DVD, disk, network) does the rest. In a VM made another
   way, put the disk before the network, or it waits at "Start PXE over IPv4":
   ```powershell
   Set-VMFirmware -VMName "Aurora" -BootOrder (Get-VMDvdDrive -VMName "Aurora"), (Get-VMHardDiskDrive -VMName "Aurora"), (Get-VMNetworkAdapter -VMName "Aurora")
   ```
5. How the installed disk starts: the installer puts Debian's signed chain (shim and
   GRUB) both in `\EFI\debian` and in the disk's fallback path `\EFI\BOOT`
   (Debian's `--force-extra-removable`). On Hyper-V with Secure Boot off, the fallback
   path starts GRUB itself, not shim: shim there runs for about 45 seconds in silence and
   hands back to the firmware ("The boot loader did not load an operating system"). On
   Hyper-V the installer also writes **no** boot entry into
   the VM's firmware and removes the one the installer's bootloader step creates:
   Hyper-V then starts the disk through its own "EFI SCSI Device" entry. Entries
   written by the guest are a known source of trouble there ([Debian
   #949751](https://bugs.debian.org/949751)), and they sent the VM to PXE after
   installing. Package updates keep both paths and never add an entry. This is
   tested in QEMU with Hyper-V's SMBIOS identity, which exercises the installer's
   behavior but not Hyper-V's firmware itself.

The Hyper-V integration daemons are already in Aurora: clean shutdown from Hyper-V
Manager, time sync and heartbeat work out of the box.

## 3. Use your GPU for Aurora AI

This is the recommended way. The AI model runs **on Windows**, directly on your graphics
card, with the vendor's own drivers and at full speed. Aurora connects to it over the
virtual network. It works with NVIDIA, AMD and Intel cards and survives every update.

### On Windows

1. Install **Ollama** from [ollama.com](https://ollama.com). It detects your GPU by itself.
2. Download a model in PowerShell. Pick one that fits your graphics memory:

   | Graphics memory | Suggested model |
   |---|---|
   | 6–8 GB | `ollama pull llama3.1:8b` or `ollama pull qwen2.5:7b` |
   | 12–16 GB | `ollama pull qwen2.5:14b` |
   | 24 GB or more | `ollama pull qwen2.5:32b` |

3. Let the VM reach Ollama. By default it only listens to Windows itself:
   - Settings → System → About → **Advanced system settings** → **Environment Variables** →
     under *System variables*, **New**: name `OLLAMA_HOST`, value `0.0.0.0`.
   - Quit Ollama from its tray icon and start it again.
4. Open its port in the Windows firewall (PowerShell as administrator):
   ```powershell
   New-NetFirewallRule -DisplayName "Ollama for VMs" -Direction Inbound -Protocol TCP `
       -LocalPort 11434 -Action Allow -Profile Any
   ```
5. Find Windows' address as the VM sees it:
   ```powershell
   (Get-NetIPAddress -InterfaceAlias "vEthernet (Default Switch)" -AddressFamily IPv4).IPAddress
   ```
   It looks like `172.26.48.1` (it can change after Windows restarts; see
   [Troubleshooting](#troubleshooting)).

### In Aurora

1. Open **Settings → AI** and turn **Aurora AI** on.
2. As the provider, choose **OpenAI-compatible API**.
3. **Service**: "Ollama on this computer", then change the **API address** to Windows'
   address from step 5: `http://172.26.48.1:11434/v1`. Press Enter to apply.
4. **Model**: the name you downloaded, for example `qwen2.5:14b`. Leave the API key empty.
5. Try it: press **Super+Shift+Space** for the Assistant, or type `? what is btrfs` in
   Spotlight (**Super**).

To check the connection from Aurora's terminal:

```sh
curl http://172.26.48.1:11434/v1/models
```

It should list your models. While the Assistant answers, Task Manager on Windows shows
your GPU busy.

## 4. Advanced: GPU partitioning inside the VM (experimental)

Hyper-V can also give a slice of the GPU to a VM (GPU-P). **Microsoft supports this only
for Windows VMs and WSL.** For a Linux VM like Aurora it relies on Microsoft's `dxgkrnl`
driver, which isn't part of Linux or Debian and has to be built by hand, and on copying
driver files from Windows. It gives compute only (CUDA, DirectML, OpenCL through D3D12),
**not** a faster screen, and it can break with every Windows driver or kernel update.
Use part 3 unless you need the GPU inside Linux itself. Only do this on an **installed**
Aurora, not the live system.

### On Windows (VM turned off, PowerShell as administrator)

```powershell
$vm = "Aurora"
Set-VM -VMName $vm -GuestControlledCacheTypes $true -LowMemoryMappedIoSpace 1GB `
       -HighMemoryMappedIoSpace 32GB -AutomaticStopAction TurnOff -CheckpointType Disabled
Add-VMGpuPartitionAdapter -VMName $vm
Get-VMGpuPartitionAdapter -VMName $vm   # check it's there
```

Then copy the driver files the VM will need into a folder, for example `C:\VMs\gpu`:

- the whole folder `C:\Windows\System32\lxss\lib` (the Linux user-space libraries Windows
  ships for WSL, such as `libdxcore.so`, `libd3d12.so` and, with NVIDIA, `libcuda.so`);
- your GPU driver's folder from `C:\Windows\System32\DriverStore\FileRepository\`. For
  NVIDIA it starts with `nv_dispi.inf_amd64_…`; to find it, look up the path of
  `nvapi64.dll` in Device Manager → your GPU → Driver → Driver Details.

### In Aurora (installed, with internet)

1. Copy the files into the VM (a shared folder, a USB stick or `scp`):
   ```sh
   sudo mkdir -p /usr/lib/wsl/lib /usr/lib/wsl/drivers
   sudo cp -r lib/* /usr/lib/wsl/lib/
   sudo cp -r nv_dispi.inf_amd64_* /usr/lib/wsl/drivers/
   echo /usr/lib/wsl/lib | sudo tee /etc/ld.so.conf.d/ld.wsl.conf && sudo ldconfig
   ```
2. Build and load the `dxgkrnl` kernel driver with DKMS. It comes from Microsoft's WSL
   kernel; community projects package it for regular kernels (search for "dxgkrnl-dkms"
   and pick one that supports Linux 6.12):
   ```sh
   sudo apt install dkms build-essential linux-headers-amd64 git
   # follow the chosen project's instructions, then:
   sudo modprobe dxgkrnl
   ls /dev/dxg    # this device must exist
   ```
3. Check it: with NVIDIA, `/usr/lib/wsl/lib/nvidia-smi` should show your card. Then run
   Ollama or llama.cpp inside Aurora with CUDA, and point Aurora AI at
   `http://localhost:11434/v1`.

If the VM doesn't start after `Add-VMGpuPartitionAdapter`, remove it with
`Remove-VMGpuPartitionAdapter -VMName Aurora`.

## 5. Use a newer ISO in the same VM

No need to create the VM again:

1. Turn the VM off.
2. Hyper-V Manager → the VM's **Settings** → **SCSI Controller → DVD Drive** → **Image
   file** → Browse → the new ISO. Or in PowerShell:
   ```powershell
   Set-VMDvdDrive -VMName "Aurora" -Path "C:\VMs\aurora-os-0.1-amd64.iso"
   Set-VMFirmware -VMName "Aurora" -BootOrder (Get-VMDvdDrive -VMName "Aurora"), (Get-VMHardDiskDrive -VMName "Aurora"), (Get-VMNetworkAdapter -VMName "Aurora")
   ```
3. Start it: the new version's boot menu appears.

Aurora already installed on the virtual disk keeps itself up to date with **Settings →
Updates**, with no ISO needed.

### Repair an older installation

If Aurora was installed with an ISO from before 1 Oct 2026 and the VM doesn't start
from its disk (it goes to PXE, or the boot summary says "The boot loader did not load an
operating system"), you don't need to reinstall. Start the VM from a current ISO
(run the script in part 1 again: it keeps the disk), choose **Try Aurora OS**, open
the **Terminal** and paste:

```sh
ROOT=$(lsblk -nrpo NAME,FSTYPE /dev/sda | awk '$2=="btrfs"{print $1; exit}')
ESP=$(lsblk -nrpo NAME,FSTYPE /dev/sda | awk '$2=="vfat"{print $1; exit}')
sudo mount -o subvol=@ "$ROOT" /mnt
sudo mount "$ESP" /mnt/boot/efi
for d in dev proc sys run; do sudo mount --rbind /$d /mnt/$d; done
sudo mkdir -p /mnt/usr/local/lib/aurora
sudo cp /usr/local/lib/aurora/efi-install /mnt/usr/local/lib/aurora/efi-install
sudo chroot /mnt /bin/bash /usr/local/lib/aurora/efi-install --install
sudo umount -R /mnt; sudo poweroff
```

The last line of the output before `umount` must read `Aurora EFI installation:
direct`. Then, in PowerShell, remove the ISO and start from the disk:

```powershell
Set-VMDvdDrive -VMName "Aurora" -Path $null
Set-VMFirmware -VMName "Aurora" -BootOrder (Get-VMDvdDrive -VMName "Aurora"), (Get-VMHardDiskDrive -VMName "Aurora"), (Get-VMNetworkAdapter -VMName "Aurora")
Start-VM -Name "Aurora"; vmconnect.exe localhost Aurora
```

### If the installed system still doesn't start: a report

[`tools/hyperv/Get-AuroraBootReport.ps1`](tools/hyperv/Get-AuroraBootReport.ps1) collects
what shows why, without changing anything. In PowerShell **as administrator**, with the VM
turned off:

```powershell
powershell -ExecutionPolicy Bypass -File .\Get-AuroraBootReport.ps1 -Name Aurora -Boot -Seconds 60
```

It writes `aurora-boot-report` on the Desktop:

- `report.txt`: the VM, its firmware (Secure Boot and template, the boot order with the
  file each entry starts), Hyper-V's log for the VM (the firmware writes there why it
  skipped a disk), and, from the disk mounted read-only, its partitions, every file on
  the EFI system partition with its SHA-256, and GRUB's configuration;
- `screens\`: with `-Boot`, what the VM's screen showed every two seconds while starting.

Zip the folder and attach it to an issue, or ask Claude Code on that computer to read it
(see below).

### With Claude Code on the Windows computer

Claude Code can run the same PowerShell commands on the computer that hosts the VM, look at
the report and the screens, and try a fix on the VM's disk with you. Install it
(<https://claude.com/claude-code>), clone this repository, open PowerShell **as
administrator** in it, run `claude`, and ask, for example:

> Aurora OS is installed in the Hyper-V VM "Aurora" (Generation 2). After installation it
> doesn't start from its disk: the firmware goes to PXE. Read HYPERV.md and
> overlay/usr/local/lib/aurora/efi-install, run tools/hyperv/Get-AuroraBootReport.ps1
> -Boot, look at the report and the screens, and find out why. Don't change the VM or its
> disk without asking me first.

## Troubleshooting

| Problem | Fix |
|---|---|
| The installed system stays at "Start PXE over IPv4" | The network is before the disk in the VM's boot order (Hyper-V's default; `Get-VMFirmware -VMName Aurora` shows it). Put the disk before it: `Set-VMFirmware -VMName Aurora -BootOrder (Get-VMDvdDrive -VMName Aurora), (Get-VMHardDiskDrive -VMName Aurora), (Get-VMNetworkAdapter -VMName Aurora)`. |
| The boot summary says "The boot loader did not load an operating system" for the disk | An installation from before 1 Oct 2026 starts shim, which doesn't work on Hyper-V with Secure Boot off: see "Repair an older installation". `tools/hyperv/Test-AuroraBoot.ps1` shows how far the boot loader gets. |
| "The image's hash and certificate are not allowed" | Keep Secure Boot **off**: `Set-VMFirmware -VMName Aurora -EnableSecureBoot Off`. |
| After installing, with the ISO removed, the VM shows "Start PXE over IPv4" | Make "Hard Drive" the first boot device (step 4). Installations made with ISOs from before 29 Sep 2026 wrote a firmware boot entry that Hyper-V can't start: reinstall with a current ISO, or start the live ISO and run, in its terminal, the commands in [Repair an older installation](#repair-an-older-installation). |
| Black window after the boot menu | Turn **Enhanced Session** off (View menu). If it stays black, pick **Try Aurora OS (safe graphics)**. |
| Small screen | `Set-VMVideo -VMName Aurora -HorizontalResolution 1920 -VerticalResolution 1080 -ResolutionType Single` with the VM off. |
| Slow or stuttering desktop | Give the VM 4 processors and static memory. The virtual display has no 3D, so Aurora uses a software renderer made for it. |
| Flickering windows or cursor trails | Check that you booted an ISO from 29 Sep 2026 or later and that Enhanced Session is off. In Aurora's terminal, `tr '\0' '\n' </proc/$(pgrep -xo wayfire)/environ \| grep LP_NUM_THREADS` must print `LP_NUM_THREADS=0`. If it still flickers, send `~/.local/state/aurora/compositor-failure.log` and a short phone video of the screen, and use labwc meanwhile: `echo labwc > ~/.config/aurora/compositor`, then log out and in. |
| No network | The VM's network adapter must use "Default Switch" (or an external switch). |
| Aurora AI can't reach Ollama | Check `OLLAMA_HOST=0.0.0.0`, the firewall rule, and Windows' address: it can change when Windows restarts. Run the `Get-NetIPAddress` command again and update the address in Settings → AI. For a fixed address, create an *External* virtual switch and use your PC's LAN address instead. |
| Answers are slow | Use a smaller model, or check in Task Manager that Ollama is using the GPU, not the CPU. |
