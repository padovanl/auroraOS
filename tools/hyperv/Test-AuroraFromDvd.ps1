<#
.SYNOPSIS
    Starts a logging UEFI Shell from the VM's DVD drive (which this firmware
    does start) and lets it start Aurora's GRUB from the hard disk.

.DESCRIPTION
    Run in PowerShell as administrator, with aurora-diag.iso and grub-min.efi
    next to this script.

      1. Aurora's EFI system partition gets a marker file, grub-min.efi and a
         GRUB configuration that notes each step in a file and loads the kernel
         itself (the original configuration is kept and put back).
      2. aurora-diag.iso goes in the DVD drive and the VM starts from it. Its
         shell writes a log on every disk it sees, saves the list of devices,
         and starts grub-min.efi from the hard disk.
      3. The logs are read and printed; the ISO is taken out and everything is
         put back.

    Everything is printed and saved in aurora-dvd-test on the Desktop.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Test-AuroraFromDvd.ps1 -Name Aurora
#>
param(
    [string]$Name = "Aurora",
    [string]$Iso = (Join-Path $PSScriptRoot "aurora-diag.iso"),
    [string]$Grub = (Join-Path $PSScriptRoot "grub-min.efi"),
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-dvd-test"),
    [int]$Seconds = 100
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}
foreach ($needed in @($Iso, $Grub)) { if (-not (Test-Path $needed)) { Write-Error "Missing: $needed" } }

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$verdict = Join-Path $Out "verdict.txt"
"Aurora OS boot from DVD shell - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $verdict
function Say($text) { Write-Host $text; $text | Add-Content -Encoding UTF8 $verdict }

$vm = Get-VM -Name $Name
if ($vm.State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
$auroraVhd = (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1).Path
$esptype = "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}"
$ascii = New-Object Text.ASCIIEncoding
Say "VM $Name, Aurora's disk $auroraVhd"

function With-Esp($vhd, [scriptblock]$action) {
    # Runs $action with the folder where the disk's EFI system partition is mounted.
    $mounted = Mount-VHD -Path $vhd -NoDriveLetter -Passthru
    try {
        $number = ($mounted | Get-Disk).Number
        $esp = Get-Partition -DiskNumber $number | Where-Object { $_.GptType -eq $esptype } | Select-Object -First 1
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

$script:original = @()
$kept = Join-Path $Out "aurora-esp-backup"
With-Esp $auroraVhd {
    param($esp)
    $cfg = Join-Path $esp "EFI\debian\grub.cfg"
    if (-not (Test-Path $kept)) {
        New-Item -ItemType Directory -Force -Path $kept | Out-Null
        Copy-Item $cfg (Join-Path $kept "grub.cfg")
    }
    $script:original = @(Get-Content (Join-Path $kept "grub.cfg"))
    $search = $script:original | Where-Object { $_ -match "^search" } | Select-Object -First 1
    $uuid = ($search -split "\s+")[1]
    [IO.File]::WriteAllText((Join-Path $esp "aurora-probe.id"), "probe`r`n", $ascii)
    Copy-Item $Grub (Join-Path $esp "EFI\BOOT\grub-min.efi") -Force
    $save = 'save_env -f ($espdev)/EFI/debian/trace.env step found kernel'
    $lines = @(
        'set espdev=$root', "set found=none", "set kernel=unknown",
        "set step=1-grub-started", $save,
        "search.fs_uuid $uuid root", 'set found=$root', "set step=2-system-partition-found", $save,
        'if [ -e ($root)/@/vmlinuz ]; then set kernel=readable; else set kernel=NOT-FOUND; fi',
        "set step=3-loading-kernel", $save,
        ('linux ($root)/@/vmlinuz root=UUID=' + $uuid + ' rootflags=subvol=@ ro'),
        "set step=4-kernel-loaded", $save,
        'initrd ($root)/@/initrd.img',
        "set step=5-initrd-loaded-starting-linux", $save,
        "boot",
        "set step=6-boot-returned", $save
    )
    [IO.File]::WriteAllText($cfg, (($lines -join "`n") + "`n"), $ascii)
    $header = "# GRUB Environment Block`n"
    [IO.File]::WriteAllText((Join-Path $esp "EFI\debian\trace.env"), ($header + ("#" * (1024 - $header.Length))), $ascii)
}
Say "Aurora's EFI partition is ready for the test."

$dvd = Get-VMDvdDrive -VMName $Name | Select-Object -First 1
if (-not $dvd) { Add-VMDvdDrive -VMName $Name; $dvd = Get-VMDvdDrive -VMName $Name | Select-Object -First 1 }
$previousIso = $dvd.Path
$booted = $false
try {
    Set-VMDvdDrive -VMName $Name -ControllerNumber $dvd.ControllerNumber -ControllerLocation $dvd.ControllerLocation -Path $Iso
    Set-VMFirmware -VMName $Name -BootOrder (Get-VMDvdDrive -VMName $Name | Select-Object -First 1)
    $started = Get-Date
    Start-VM -Name $Name
    Start-Process vmconnect.exe -ArgumentList "localhost", $Name
    while (((Get-Date) - $started).TotalSeconds -lt $Seconds) {
        Start-Sleep -Seconds 5
        $hit = Get-WinEvent -FilterHashtable @{ LogName = "Microsoft-Windows-Hyper-V-Worker-Admin"; Id = 18601; StartTime = $started } -ErrorAction SilentlyContinue |
            Where-Object { $_.Message -match [regex]::Escape($vm.VMId.ToString()) }
        if ($hit -and -not $booted) { $booted = $true; $started = (Get-Date).AddSeconds(30 - $Seconds) }
    }
    Say "Hyper-V says an operating system started: $booted"
} finally {
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    Set-VMDvdDrive -VMName $Name -ControllerNumber $dvd.ControllerNumber -ControllerLocation $dvd.ControllerLocation -Path $previousIso
    With-Esp $auroraVhd {
        param($esp)
        Say "--- what was written on Aurora's EFI partition ---"
        foreach ($log in @("dvd1.log", "dvd2.log", "dvd3.log")) {
            $path = Join-Path $esp $log
            if (Test-Path $path) { Say ("  {0}: {1}" -f $log, ((Get-Content $path -Encoding Unicode -Raw) -replace "\s+", " ").Trim()) }
            else { Say "  ${log}: (not written)" }
        }
        $map = Join-Path $esp "dvd-map.log"
        if (Test-Path $map) {
            Say "  devices the firmware shows to the shell ('map'):"
            (Get-Content $map -Encoding Unicode) | Where-Object { $_.Trim() } | ForEach-Object { Say ("    " + $_.TrimEnd()) }
        } else { Say "  dvd-map.log: (not written)" }
        $trace = Join-Path $esp "EFI\debian\trace.env"
        if (Test-Path $trace) {
            $steps = (((Get-Content $trace -Raw) -replace "#", "").Trim() -split "`n" | Where-Object { $_ -notmatch "GRUB Environment Block" })
            if ($steps) { $steps | ForEach-Object { Say ("  GRUB: " + $_.Trim()) } } else { Say "  GRUB: (no step written)" }
        }
        Say "--- end ---"
        Copy-Item (Join-Path $kept "grub.cfg") (Join-Path $esp "EFI\debian\grub.cfg") -Force
        foreach ($leftover in @("aurora-probe.id", "dvd1.log", "dvd2.log", "dvd3.log", "dvd-map.log",
                                "EFI\BOOT\grub-min.efi", "EFI\debian\trace.env")) {
            Remove-Item (Join-Path $esp $leftover) -ErrorAction SilentlyContinue
        }
    }
    $order = @(Get-VMDvdDrive -VMName $Name) + @(Get-VMHardDiskDrive -VMName $Name) + @(Get-VMNetworkAdapter -VMName $Name)
    Set-VMFirmware -VMName $Name -BootOrder $order
}
Say "Aurora's EFI partition, the DVD drive and the boot order (DVD, disk, network) are as before."
Say "Folder: $Out"
