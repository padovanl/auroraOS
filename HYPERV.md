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
Set-VMFirmware -VMName $vm -FirstBootDevice (Get-VMDvdDrive -VMName $vm) -EnableSecureBoot Off
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
| Secure Boot **off** | Required for the live ISO and for the direct GRUB boot path installed on Hyper-V. Keep it off after installation. |
| 1920×1080 | Hyper-V's default screen is small. Pick your monitor's resolution. |
| Enhanced session off | Enhanced session (RDP) doesn't work with Aurora's Wayland desktop and would show a black window. |

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
   Set-VMFirmware -VMName "Aurora" -FirstBootDevice (Get-VMHardDiskDrive -VMName "Aurora" | Select-Object -First 1)
   ```
5. Keep Secure Boot **off**. On Hyper-V with Secure Boot disabled, the installer
   installs GRUB directly in both the Debian EFI directory and the disk fallback
   path, avoiding the shim handoff. Package updates refresh both paths. Other
   UEFI systems retain Debian's signed shim chain. This policy is tested with
   Hyper-V SMBIOS identity in QEMU; that does not emulate Hyper-V firmware.

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
   Set-VMFirmware -VMName "Aurora" -FirstBootDevice (Get-VMDvdDrive -VMName "Aurora")
   ```
3. Start it: the new version's boot menu appears.

Aurora already installed on the virtual disk keeps itself up to date with **Settings →
Updates**, with no ISO needed.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Start PXE over IPv4", "The image's hash and certificate are not allowed", or the VM starts from the network | Keep Secure Boot **off**: `Set-VMFirmware -VMName Aurora -EnableSecureBoot Off`. To install, put the DVD first; after installation, remove the ISO. |
| After installing, with the ISO removed, the VM shows "Start PXE over IPv4" | Check that the installed VHDX is attached and Secure Boot is off. The current installer writes and checks both EFI paths; older installations are not repaired merely by attaching a new ISO. |
| Black window after the boot menu | Turn **Enhanced Session** off (View menu). If it stays black, pick **Try Aurora OS (safe graphics)**. |
| Small screen | `Set-VMVideo -VMName Aurora -HorizontalResolution 1920 -VerticalResolution 1080 -ResolutionType Single` with the VM off. |
| Slow or stuttering desktop | Give the VM 4 processors and static memory. The virtual display has no 3D, so Aurora uses a software renderer made for it. |
| No network | The VM's network adapter must use "Default Switch" (or an external switch). |
| Aurora AI can't reach Ollama | Check `OLLAMA_HOST=0.0.0.0`, the firewall rule, and Windows' address: it can change when Windows restarts. Run the `Get-NetIPAddress` command again and update the address in Settings → AI. For a fixed address, create an *External* virtual switch and use your PC's LAN address instead. |
| Answers are slow | Use a smaller model, or check in Task Manager that Ollama is using the GPU, not the CPU. |
