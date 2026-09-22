<#
.SYNOPSIS
    Runs the same logging boot chain from a disk made by Windows and from
    Aurora's disk, to see which one the Hyper-V firmware can start.

.DESCRIPTION
    Run in PowerShell as administrator, with shellx64.efi and grub-min.efi next
    to this script. The chain is: UEFI Shell (writes log files, lists the disks
    the firmware sees) -> GRUB (notes each step in a file) -> Aurora's kernel.
    Nothing depends on what the screen shows.

      Try 1: a new 1 GB disk formatted by Windows, added to the VM.
      Try 2: the EFI system partition of Aurora's own disk (its files are
             kept and put back).

    Everything is printed and saved in aurora-matrix-test on the Desktop.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Test-AuroraMatrix.ps1 -Name Aurora
#>
param(
    [string]$Name = "Aurora",
    [string]$Shell = (Join-Path $PSScriptRoot "shellx64.efi"),
    [string]$Grub = (Join-Path $PSScriptRoot "grub-min.efi"),
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-matrix-test"),
    [int]$Seconds = 100
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}
foreach ($needed in @($Shell, $Grub)) { if (-not (Test-Path $needed)) { Write-Error "Missing: $needed" } }

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$verdict = Join-Path $Out "verdict.txt"
"Aurora OS boot matrix - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $verdict
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

# What GRUB needs to find Aurora's system partition, from Aurora's own configuration.
$script:original = @()
With-Esp $auroraVhd {
    param($esp)
    $cfg = Join-Path $esp "EFI\debian\grub.cfg"
    $source = if (Test-Path "$cfg.aurora-backup") { "$cfg.aurora-backup" } else { $cfg }
    $script:original = @(Get-Content $source)
}
$search = $script:original | Where-Object { $_ -match "^search" } | Select-Object -First 1
$uuid = ($search -split "\s+")[1]
Say "Aurora's system partition: UUID $uuid"

function Put-Chain($esp) {
    New-Item -ItemType Directory -Force -Path (Join-Path $esp "EFI\BOOT"), (Join-Path $esp "EFI\debian") | Out-Null
    [IO.File]::WriteAllText((Join-Path $esp "aurora-probe.id"), "probe`r`n", $ascii)
    $nsh = @(
        "@echo -off",
        "for %i in fs0 fs1 fs2 fs3 fs4",
        "  if exist %i:\aurora-probe.id then",
        '    echo "shell-started" > %i:\shell1.log',
        "    map > %i:\shell-map.log",
        '    echo "starting-grub" > %i:\shell2.log',
        "    %i:\EFI\BOOT\grub-min.efi",
        '    echo "grub-returned %lasterror%" > %i:\shell3.log',
        "  endif",
        "endfor"
    )
    [IO.File]::WriteAllText((Join-Path $esp "startup.nsh"), (($nsh -join "`r`n") + "`r`n"), $ascii)
    Copy-Item $Shell (Join-Path $esp "EFI\BOOT\BOOTX64.EFI") -Force
    Copy-Item $Grub (Join-Path $esp "EFI\BOOT\grub-min.efi") -Force
    $save = 'save_env -f ($espdev)/EFI/debian/trace.env step found kernel'
    $cfg = @(
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
    [IO.File]::WriteAllText((Join-Path $esp "EFI\debian\grub.cfg"), (($cfg -join "`n") + "`n"), $ascii)
    $header = "# GRUB Environment Block`n"
    [IO.File]::WriteAllText((Join-Path $esp "EFI\debian\trace.env"), ($header + ("#" * (1024 - $header.Length))), $ascii)
}

function Read-Chain($esp) {
    foreach ($log in @("shell1.log", "shell2.log", "shell3.log")) {
        $path = Join-Path $esp $log
        if (Test-Path $path) { Say ("  {0}: {1}" -f $log, ((Get-Content $path -Encoding Unicode -Raw) -replace "\s+", " ").Trim()) }
        else { Say "  ${log}: (not written)" }
    }
    $map = Join-Path $esp "shell-map.log"
    if (Test-Path $map) {
        Say "  disks the firmware sees (shell 'map'):"
        (Get-Content $map -Encoding Unicode) | Where-Object { $_.Trim() } | ForEach-Object { Say ("    " + $_.TrimEnd()) }
    } else { Say "  shell-map.log: (not written)" }
    $trace = Join-Path $esp "EFI\debian\trace.env"
    if (Test-Path $trace) {
        $steps = (((Get-Content $trace -Raw) -replace "#", "").Trim() -split "`n" | Where-Object { $_ -notmatch "GRUB Environment Block" })
        if ($steps) { $steps | ForEach-Object { Say ("  GRUB: " + $_.Trim()) } } else { Say "  GRUB: (no step written: it never ran its configuration)" }
    }
}

function Start-Try($label, $bootDrive) {
    Set-VMFirmware -VMName $Name -BootOrder $bootDrive
    $started = Get-Date
    Start-VM -Name $Name
    $booted = $false
    while (((Get-Date) - $started).TotalSeconds -lt $Seconds) {
        Start-Sleep -Seconds 5
        $hit = Get-WinEvent -FilterHashtable @{ LogName = "Microsoft-Windows-Hyper-V-Worker-Admin"; Id = 18601; StartTime = $started } -ErrorAction SilentlyContinue |
            Where-Object { $_.Message -match [regex]::Escape($vm.VMId.ToString()) }
        if ($hit -and -not $booted) { $booted = $true; $started = (Get-Date).AddSeconds(25 - $Seconds) }
    }
    # A clean stop where possible, so files the shell wrote are on the disk.
    Stop-VM -Name $Name -TurnOff -Force
    Say ("{0}: Hyper-V says an operating system started: {1}" -f $label, $booted)
}

# --- Try 1: a disk made by Windows -----------------------------------------------------------
Say ""
Say "=== Try 1: the chain on a new disk formatted by Windows ==="
$probe = Join-Path $Out "probe.vhdx"
if (Test-Path $probe) { Remove-Item $probe -Force }
New-VHD -Path $probe -SizeBytes 1GB -Dynamic | Out-Null
$disk = Mount-VHD -Path $probe -NoDriveLetter -Passthru | Get-Disk
try {
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT
    Get-Partition -DiskNumber $disk.Number -ErrorAction SilentlyContinue |
        Remove-Partition -Confirm:$false -ErrorAction SilentlyContinue
    $part = New-Partition -DiskNumber $disk.Number -UseMaximumSize
    Format-Volume -Partition $part -FileSystem FAT32 -NewFileSystemLabel "PROBE" -Force -Confirm:$false | Out-Null
    Set-Partition -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -GptType $esptype
} finally {
    Dismount-VHD -Path $probe
}
With-Esp $probe { param($esp) Put-Chain $esp }
$added = $null
try {
    $added = Add-VMHardDiskDrive -VMName $Name -ControllerType SCSI -Path $probe -Passthru
    Start-Try "Try 1" $added
} finally {
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    if ($added) { Remove-VMHardDiskDrive -VMHardDiskDrive $added }
}
With-Esp $probe { param($esp) Read-Chain $esp }

# --- Try 2: Aurora's own EFI partition ---------------------------------------------------------
Say ""
Say "=== Try 2: the same chain on Aurora's own EFI partition ==="
$kept = Join-Path $Out "aurora-esp-backup"
With-Esp $auroraVhd {
    param($esp)
    if (-not (Test-Path $kept)) {
        New-Item -ItemType Directory -Force -Path $kept | Out-Null
        Copy-Item (Join-Path $esp "EFI\debian\grub.cfg") (Join-Path $kept "grub.cfg")
        Copy-Item (Join-Path $esp "EFI\BOOT\BOOTX64.EFI") (Join-Path $kept "BOOTX64.EFI")
    }
    Put-Chain $esp
}
try {
    Start-Try "Try 2" (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1)
} finally {
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    With-Esp $auroraVhd {
        param($esp)
        Read-Chain $esp
        Copy-Item (Join-Path $kept "grub.cfg") (Join-Path $esp "EFI\debian\grub.cfg") -Force
        Copy-Item (Join-Path $kept "BOOTX64.EFI") (Join-Path $esp "EFI\BOOT\BOOTX64.EFI") -Force
        foreach ($leftover in @("aurora-probe.id", "startup.nsh", "shell1.log", "shell2.log", "shell3.log",
                                "shell-map.log", "EFI\BOOT\grub-min.efi", "EFI\debian\trace.env")) {
            Remove-Item (Join-Path $esp $leftover) -ErrorAction SilentlyContinue
        }
    }
    $order = @(Get-VMDvdDrive -VMName $Name) + @(Get-VMHardDiskDrive -VMName $Name) + @(Get-VMNetworkAdapter -VMName $Name)
    Set-VMFirmware -VMName $Name -BootOrder $order
}
Say ""
Say "Aurora's EFI partition and the boot order (DVD, disk, network) are as before."
Say "Folder: $Out"
