<#
.SYNOPSIS
    Records in a file how far the boot loader gets on an installed Aurora OS in
    Hyper-V, without relying on what the screen shows.

.DESCRIPTION
    Run in PowerShell as administrator, with grub-min.efi next to this script.

      1. On the EFI system partition of Aurora's disk, GRUB's configuration is
         replaced by one that notes each step in a file (trace.env) and then
         loads the kernel itself; BOOTX64.EFI becomes grub-min.efi. The
         originals are kept next to them.
      2. The VM starts from the disk, in a window so the screen can be watched.
      3. The VM is turned off, the trace is read and printed, and the original
         files and a normal boot order are put back.

    Results go to aurora-trace-test on the Desktop (verdict.txt, screens).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Test-AuroraTrace.ps1 -Name Aurora
#>
param(
    [string]$Name = "Aurora",
    [string]$Grub = (Join-Path $PSScriptRoot "grub-min.efi"),
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-trace-test"),
    [int]$Seconds = 100
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}
if (-not (Test-Path $Grub)) { Write-Error "GRUB image not found: $Grub" }
Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$verdict = Join-Path $Out "verdict.txt"
"Aurora OS boot trace - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $verdict
function Say($text) { Write-Host $text; $text | Add-Content -Encoding UTF8 $verdict }

$vm = Get-VM -Name $Name
if ($vm.State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
$vhd = (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1).Path
Say "VM $Name, disk $vhd"

function Edit-Esp([scriptblock]$action) {
    $mounted = Mount-VHD -Path $vhd -NoDriveLetter -Passthru
    try {
        $number = ($mounted | Get-Disk).Number
        $esp = Get-Partition -DiskNumber $number |
            Where-Object { $_.GptType -eq "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}" } | Select-Object -First 1
        if (-not $esp) { throw "no EFI system partition on $vhd" }
        $mountPoint = Join-Path $env:TEMP "aurora-esp"
        New-Item -ItemType Directory -Force -Path $mountPoint | Out-Null
        Add-PartitionAccessPath -DiskNumber $number -PartitionNumber $esp.PartitionNumber -AccessPath $mountPoint
        try { & $action $mountPoint }
        finally {
            Remove-PartitionAccessPath -DiskNumber $number -PartitionNumber $esp.PartitionNumber -AccessPath $mountPoint -ErrorAction SilentlyContinue
        }
    } finally {
        Dismount-VHD -Path $vhd
    }
}

function Save-Screen($file) {
    $service = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_VirtualSystemManagementService
    $settings = Get-CimInstance -Namespace root\virtualization\v2 -ClassName Msvm_VirtualSystemSettingData |
        Where-Object { $_.ElementName -eq $Name -and $_.VirtualSystemType -eq "Microsoft:Hyper-V:System:Realized" }
    $w = 1024; $h = 768
    $result = Invoke-CimMethod -InputObject $service -MethodName GetVirtualSystemThumbnailImage `
        -Arguments @{ TargetSystem = $settings; WidthPixels = [uint16]$w; HeightPixels = [uint16]$h }
    if (-not $result.ImageData) { return }
    $bmp = New-Object System.Drawing.Bitmap($w, $h, [System.Drawing.Imaging.PixelFormat]::Format16bppRgb565)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $w, $h)
    $data = $bmp.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::WriteOnly, $bmp.PixelFormat)
    [System.Runtime.InteropServices.Marshal]::Copy([byte[]]$result.ImageData, 0, $data.Scan0, [math]::Min($result.ImageData.Length, $data.Stride * $h))
    $bmp.UnlockBits($data)
    $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

# --- 1. GRUB that writes down each step ---------------------------------------------------
Edit-Esp {
    param($esp)
    $cfg = Join-Path $esp "EFI\debian\grub.cfg"
    if (-not (Test-Path "$cfg.aurora-backup")) { Copy-Item $cfg "$cfg.aurora-backup" }
    $boot = Join-Path $esp "EFI\BOOT\BOOTX64.EFI"
    if (-not (Test-Path "$boot.aurora-backup")) { Copy-Item $boot "$boot.aurora-backup" }
    $original = Get-Content "$cfg.aurora-backup"
    $search = $original | Where-Object { $_ -match "^search" } | Select-Object -First 1
    $prefix = $original | Where-Object { $_ -match "^set prefix" } | Select-Object -First 1
    $uuid = ($search -split "\s+")[1]
    $save = 'save_env -f ($espdev)/EFI/debian/trace.env step found menu kernel'
    $lines = @(
        'set espdev=$root', "set found=none", "set menu=unknown", "set kernel=unknown",
        "set step=1-grub-started", $save,
        $search, 'set found=$root', "set step=2-system-partition-found", $save,
        $prefix,
        'if [ -e $prefix/grub.cfg ]; then set menu=readable; else set menu=MISSING; fi',
        'if [ -e ($root)/@/vmlinuz ]; then set kernel=readable; else set kernel=NOT-FOUND; fi',
        "set step=3-files-checked", $save,
        "set step=4-loading-kernel", $save,
        ('linux ($root)/@/vmlinuz root=UUID=' + $uuid + ' rootflags=subvol=@ ro'),
        "set step=5-kernel-loaded", $save,
        'initrd ($root)/@/initrd.img',
        "set step=6-initrd-loaded-starting-linux", $save,
        "boot",
        "set step=7-boot-returned", $save
    )
    $ascii = New-Object Text.ASCIIEncoding
    [IO.File]::WriteAllText($cfg, (($lines -join "`n") + "`n"), $ascii)
    # GRUB only writes into an existing 1024-byte environment block.
    $header = "# GRUB Environment Block`n"
    [IO.File]::WriteAllText((Join-Path $esp "EFI\debian\trace.env"), ($header + ("#" * (1024 - $header.Length))), $ascii)
    Copy-Item $Grub $boot -Force
}
Say "The EFI partition now has the tracing GRUB."

# --- 2. start ------------------------------------------------------------------------------
$booted = $false
try {
    Set-VMFirmware -VMName $Name -BootOrder (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1)
    $shots = Join-Path $Out "screens"
    New-Item -ItemType Directory -Force -Path $shots | Out-Null
    $started = Get-Date
    Start-VM -Name $Name
    Start-Process vmconnect.exe -ArgumentList "localhost", $Name
    $n = 0
    while (((Get-Date) - $started).TotalSeconds -lt $Seconds) {
        Start-Sleep -Milliseconds 700
        $n++
        try { Save-Screen (Join-Path $shots ("{0:D3}.png" -f $n)) } catch { }
        if ($n % 5 -eq 0 -and -not $booted) {
            $hit = Get-WinEvent -FilterHashtable @{ LogName = "Microsoft-Windows-Hyper-V-Worker-Admin"; Id = 18601; StartTime = $started } -ErrorAction SilentlyContinue |
                Where-Object { $_.Message -match [regex]::Escape($vm.VMId.ToString()) }
            if ($hit) { $booted = $true }
        }
    }
    Say ("Hyper-V says an operating system started: {0} ({1} screens)" -f $booted, $n)
} finally {
    # --- 3. read the trace, put things back ---------------------------------------------------
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    Edit-Esp {
        param($esp)
        $trace = Join-Path $esp "EFI\debian\trace.env"
        Say "--- trace written by GRUB ---"
        if (Test-Path $trace) {
            ((Get-Content $trace -Raw) -replace "#", "").Trim() -split "`n" | ForEach-Object { Say ("  " + $_) }
            Remove-Item $trace
        } else { Say "  (no trace file)" }
        Say "--- end of trace ---"
        $cfg = Join-Path $esp "EFI\debian\grub.cfg"
        if (Test-Path "$cfg.aurora-backup") { Copy-Item "$cfg.aurora-backup" $cfg -Force; Remove-Item "$cfg.aurora-backup" }
        $boot = Join-Path $esp "EFI\BOOT\BOOTX64.EFI"
        if (Test-Path "$boot.aurora-backup") { Copy-Item "$boot.aurora-backup" $boot -Force; Remove-Item "$boot.aurora-backup" }
    }
    $order = @(Get-VMDvdDrive -VMName $Name) + @(Get-VMHardDiskDrive -VMName $Name) + @(Get-VMNetworkAdapter -VMName $Name)
    Set-VMFirmware -VMName $Name -BootOrder $order
}
Say "A trace with only the 'GRUB Environment Block' line means GRUB never ran."
Say "Folder: $Out"
