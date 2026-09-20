<#
.SYNOPSIS
    Finds where an installed Aurora OS stops while starting in Hyper-V, by trying.

.DESCRIPTION
    Run in PowerShell as administrator, with Aurora already installed on the
    VM's disk. Unlike Get-AuroraBootReport.ps1 this one changes things, and puts
    them back:

      1. GRUB's small configuration on the EFI system partition gets numbered
         messages (the original is kept next to it and restored at the end),
         so the screen shows how far the boot loader gets;
      2. the VM starts from its disk with its DVD drive as it is, and the
         screen is saved about once a second;
      3. the DVD drive is removed and the VM starts again;
      4. GRUB's configuration and a normal boot order are restored. If the VM
         only starts without the DVD drive, it is left without one (working);
         otherwise the drive is put back.

    Results go to aurora-boot-test on the Desktop: verdict.txt and the screens
    of each try.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Test-AuroraBoot.ps1 -Name Aurora
#>
param(
    [string]$Name = "Aurora",
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-boot-test"),
    [int]$Seconds = 75
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}
Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$verdict = Join-Path $Out "verdict.txt"
"Aurora OS boot test - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $verdict
function Say($text) { Write-Host $text; $text | Add-Content -Encoding UTF8 $verdict }

$vm = Get-VM -Name $Name
if ($vm.State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
$disk = Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1
$vhd = $disk.Path
$dvds = @(Get-VMDvdDrive -VMName $Name | ForEach-Object {
    @{ Number = $_.ControllerNumber; Location = $_.ControllerLocation; Path = $_.Path } })
Say "VM $Name, disk $vhd, DVD drives: $($dvds.Count) (media: $(($dvds | ForEach-Object { if ($_.Path) { $_.Path } else { 'none' } }) -join ', '))"

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

function Test-Boot($label) {
    # Start from the disk; $true when Hyper-V logs that an operating system took over.
    $shots = Join-Path $Out $label
    New-Item -ItemType Directory -Force -Path $shots | Out-Null
    Set-VMFirmware -VMName $Name -BootOrder (Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1)
    $started = Get-Date
    Start-VM -Name $Name
    $booted = $false
    $n = 0
    while (((Get-Date) - $started).TotalSeconds -lt $Seconds) {
        Start-Sleep -Milliseconds 700
        $n++
        try { Save-Screen (Join-Path $shots ("{0:D3}.png" -f $n)) } catch { }
        if ($n % 5 -eq 0 -and -not $booted) {
            $hit = Get-WinEvent -FilterHashtable @{ LogName = "Microsoft-Windows-Hyper-V-Worker-Admin"; Id = 18601; StartTime = $started } -ErrorAction SilentlyContinue |
                Where-Object { $_.Message -match [regex]::Escape($vm.VMId.ToString()) }
            if ($hit) {
                $booted = $true
                # A few more screens: the menu, the kernel, the desktop.
                $started = (Get-Date).AddSeconds(20 - $Seconds)
            }
        }
    }
    Stop-VM -Name $Name -TurnOff -Force
    Say ("{0}: {1} ({2} screens in {3})" -f $label, $(if ($booted) { "an operating system started" } else { "NO operating system started" }), $n, $shots)
    return $booted
}

function Edit-Esp([scriptblock]$action) {
    # Runs $action with the path of the mounted EFI system partition.
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

# --- 1. numbered messages in GRUB's first configuration -------------------------------
Edit-Esp {
    param($esp)
    $cfg = Join-Path $esp "EFI\debian\grub.cfg"
    $backup = "$cfg.aurora-backup"
    if (-not (Test-Path $backup)) { Copy-Item $cfg $backup }
    $original = Get-Content $backup
    $search = $original | Where-Object { $_ -match "^search" } | Select-Object -First 1
    $prefix = $original | Where-Object { $_ -match "^set prefix" } | Select-Object -First 1
    $lines = @(
        "set pager=0",
        "echo 'AURORA 1: GRUB started from the EFI partition'",
        "echo 'AURORA 2: looking for the system partition...'",
        $search,
        'echo "AURORA 3: found it: root=$root"',
        $prefix,
        "echo 'AURORA 4: reading its /boot/grub folder...'",
        'ls $prefix/',
        "echo 'AURORA 5: loading the boot menu...'",
        'configfile $prefix/grub.cfg',
        "echo 'AURORA 6: the boot menu returned'"
    )
    [IO.File]::WriteAllText($cfg, (($lines -join "`n") + "`n"), (New-Object Text.ASCIIEncoding))
}
Say "GRUB's configuration on the EFI partition now prints numbered messages."

$withDvd = $false
$withoutDvd = $false
try {
    # --- 2. as the VM is ---------------------------------------------------------------
    $withDvd = Test-Boot "1-with-dvd-drive"

    # --- 3. without the DVD drive ------------------------------------------------------
    if (-not $withDvd -and $dvds.Count -gt 0) {
        Get-VMDvdDrive -VMName $Name | Remove-VMDvdDrive
        $withoutDvd = Test-Boot "2-without-dvd-drive"
    }
} finally {
    # --- 4. put things back -------------------------------------------------------------
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    Edit-Esp {
        param($esp)
        $cfg = Join-Path $esp "EFI\debian\grub.cfg"
        $backup = "$cfg.aurora-backup"
        if (Test-Path $backup) { Copy-Item $backup $cfg -Force; Remove-Item $backup }
    }
    if (-not $withoutDvd -and -not (Get-VMDvdDrive -VMName $Name)) {
        foreach ($d in $dvds) {
            if ($d.Path) { Add-VMDvdDrive -VMName $Name -ControllerNumber $d.Number -ControllerLocation $d.Location -Path $d.Path }
            else { Add-VMDvdDrive -VMName $Name -ControllerNumber $d.Number -ControllerLocation $d.Location }
        }
    }
    $order = @(Get-VMDvdDrive -VMName $Name) + @(Get-VMHardDiskDrive -VMName $Name) + @(Get-VMNetworkAdapter -VMName $Name)
    Set-VMFirmware -VMName $Name -BootOrder $order
}

Say ""
if ($withDvd) {
    Say "VERDICT: it starts from the disk with the DVD drive present. The boot order was the problem; it is now DVD, disk, network."
} elseif ($withoutDvd) {
    Say "VERDICT: it starts only without the DVD drive. The empty drive stalls the boot loader."
    Say "The VM is left without a DVD drive, so it works now: Start-VM -Name $Name"
    Say "(New-AuroraVM.ps1 adds the drive again when you give it a newer ISO.)"
} else {
    Say "VERDICT: it doesn't start either way. Look at the last AURORA message in the screens of each try."
}
Say "Folder: $Out"
