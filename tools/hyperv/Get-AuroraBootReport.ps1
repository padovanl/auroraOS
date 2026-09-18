<#
.SYNOPSIS
    Collects what's needed to see why an installed Aurora OS doesn't start in
    Hyper-V (for example, it goes to the network "PXE" boot instead).

.DESCRIPTION
    Run in PowerShell as administrator on the Windows computer that hosts the
    VM. It only reads: nothing in the VM or its disk is changed.

      - the VM and its firmware: Secure Boot and its template, the boot order
        with the file each entry starts;
      - Hyper-V's own log for this VM: the firmware writes there why it
        skipped a disk (an image it doesn't trust, no operating system found);
      - with the VM turned off, its disk mounted read-only: the partitions,
        every file on the EFI system partition with its SHA-256, and GRUB's
        configuration files;
      - with -Boot, it starts the VM and saves what the screen shows every two
        seconds, so the whole start can be looked at afterwards.

    Everything goes to a folder (default: aurora-boot-report on the Desktop),
    with report.txt; zip it and send it, or give it to Claude.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Get-AuroraBootReport.ps1
    powershell -ExecutionPolicy Bypass -File .\Get-AuroraBootReport.ps1 -Name Aurora -Boot -Seconds 60
#>
param(
    [string]$Name = "Aurora",
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-boot-report"),
    [switch]$Boot,
    [int]$Seconds = 60
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$report = Join-Path $Out "report.txt"
"Aurora OS boot report - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $report

function Section($title) { "`r`n===== $title =====" | Add-Content -Encoding UTF8 $report }
function Note($obj) { ($obj | Out-String -Width 220).TrimEnd() | Add-Content -Encoding UTF8 $report }

$vm = Get-VM -Name $Name
Section "VM"
Note ($vm | Select-Object Name, State, Generation, Version, ProcessorCount,
      @{n = "MemoryGB"; e = { $_.MemoryStartup / 1GB } }, Path)
Note ("Windows: " + [Environment]::OSVersion.VersionString)

Section "Firmware"
$fw = Get-VMFirmware -VMName $Name
Note ($fw | Select-Object SecureBoot, SecureBootTemplate, SecureBootTemplateId,
      PreferredNetworkBootProtocol, ConsoleMode, PauseAfterBootFailure)
Section "Boot order (first is tried first)"
$i = 0
foreach ($entry in $fw.BootOrder) {
    $i++
    $device = if ($entry.Device) { $entry.Device.GetType().Name + " " + $entry.Device.Path } else { "" }
    Note ("{0}. {1,-6} {2} | {3} | {4}" -f $i, $entry.BootType, $entry.Description, $entry.FirmwarePath, $device)
}

Section "Drives"
Note (Get-VMHardDiskDrive -VMName $Name | Select-Object ControllerType, ControllerNumber, ControllerLocation, Path)
Note (Get-VMDvdDrive -VMName $Name | Select-Object ControllerNumber, ControllerLocation, Path)

Section "Hyper-V log for this VM (newest first)"
try {
    $events = Get-WinEvent -LogName "Microsoft-Windows-Hyper-V-Worker-Admin" -MaxEvents 400 |
        Where-Object { $_.Message -match [regex]::Escape($vm.VMId.ToString()) -or $_.Message -match [regex]::Escape($Name) } |
        Select-Object -First 40
    foreach ($e in $events) { Note ("{0:s} [{1}] {2}" -f $e.TimeCreated, $e.Id, ($e.Message -replace "\s+", " ")) }
} catch { Note "Could not read the Hyper-V log: $_" }

# --- the disk, read-only ------------------------------------------------------------
$vhd = (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1).Path
Section "Disk $vhd"
if ((Get-VM -Name $Name).State -ne "Off") {
    Note "The VM is running: turn it off (Stop-VM -Name $Name) and run this again to read its disk."
} elseif ($vhd) {
    $mounted = $null
    try {
        $mounted = Mount-VHD -Path $vhd -ReadOnly -NoDriveLetter -Passthru
        $disk = $mounted | Get-Disk
        Note ($disk | Select-Object Number, PartitionStyle, Size, IsReadOnly)
        $parts = Get-Partition -DiskNumber $disk.Number
        Note ($parts | Select-Object PartitionNumber, GptType, Type, @{n = "SizeMB"; e = { [math]::Round($_.Size / 1MB) } }, IsSystem, IsBoot)
        $esp = $parts | Where-Object { $_.GptType -eq "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}" } | Select-Object -First 1
        if (-not $esp) {
            Note "No EFI system partition on this disk: the firmware has nothing to start from it."
        } else {
            $volume = $esp | Get-Volume
            Note ($volume | Select-Object FileSystem, FileSystemLabel, SizeRemaining, Size)
            # A read-only volume can still be looked at through a temporary folder.
            $mountPoint = Join-Path $env:TEMP "aurora-esp"
            New-Item -ItemType Directory -Force -Path $mountPoint | Out-Null
            Add-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $esp.PartitionNumber -AccessPath $mountPoint
            try {
                Section "EFI system partition files"
                Get-ChildItem -Recurse -File $mountPoint | ForEach-Object {
                    $hash = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.Substring(0, 16)
                    Note ("{0,-48} {1,10} {2}" -f $_.FullName.Substring($mountPoint.Length), $_.Length, $hash)
                }
                foreach ($cfg in @("EFI\debian\grub.cfg", "EFI\BOOT\grub.cfg", "EFI\aurora\grub.cfg")) {
                    $path = Join-Path $mountPoint $cfg
                    if (Test-Path $path) {
                        Section $cfg
                        Get-Content $path | Add-Content -Encoding UTF8 $report
                    }
                }
            } finally {
                Remove-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $esp.PartitionNumber -AccessPath $mountPoint -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Note "Could not read the disk: $_"
    } finally {
        if ($mounted) { Dismount-VHD -Path $vhd }
    }
}

# --- watching it start ----------------------------------------------------------------
function Save-Screen($vmName, $file) {
    # Hyper-V's thumbnail of the VM's screen, as a PNG (the image arrives as RGB565).
    Add-Type -AssemblyName System.Drawing
    $service = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_VirtualSystemManagementService
    $settings = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_VirtualSystemSettingData |
        Where-Object { $_.ElementName -eq $vmName -and $_.VirtualSystemType -eq "Microsoft:Hyper-V:System:Realized" }
    $w = 1024; $h = 768
    $result = Invoke-CimMethod -InputObject $service -MethodName GetVirtualSystemThumbnailImage `
        -Arguments @{ TargetSystem = $settings; WidthPixels = [uint16]$w; HeightPixels = [uint16]$h }
    if (-not $result.ImageData) { return $false }
    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format16bppRgb565)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bmp.PixelFormat)
    [System.Runtime.InteropServices.Marshal]::Copy([byte[]]$result.ImageData, 0, $data.Scan0, [math]::Min($result.ImageData.Length, $data.Stride * $h))
    $bmp.UnlockBits($data)
    $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    return $true
}

if ($Boot) {
    Section "Start"
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    Start-VM -Name $Name
    $shots = Join-Path $Out "screens"
    New-Item -ItemType Directory -Force -Path $shots | Out-Null
    $deadline = (Get-Date).AddSeconds($Seconds)
    $n = 0
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        $n++
        try {
            if (Save-Screen $Name (Join-Path $shots ("{0:D3}.png" -f $n))) { continue }
        } catch { Note "Screen $n not saved: $_"; break }
    }
    Note "$n screens in $shots"
    Section "Hyper-V log after starting"
    try {
        Get-WinEvent -LogName "Microsoft-Windows-Hyper-V-Worker-Admin" -MaxEvents 60 |
            Where-Object { $_.TimeCreated -gt (Get-Date).AddSeconds(-$Seconds - 30) } |
            ForEach-Object { Note ("{0:s} [{1}] {2}" -f $_.TimeCreated, $_.Id, ($_.Message -replace "\s+", " ")) }
    } catch { Note "Could not read the Hyper-V log: $_" }
}

Write-Host "Report: $report"
if ($Boot) { Write-Host "Screens: $(Join-Path $Out 'screens')" }
