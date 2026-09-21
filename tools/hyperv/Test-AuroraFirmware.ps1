<#
.SYNOPSIS
    Tells "this VM's firmware starts no disk" from "it can't start Aurora's disk".

.DESCRIPTION
    Run in PowerShell as administrator, with the UEFI Shell (shellx64.efi) next
    to this script. Aurora's disk is not changed.

      1. a new 1 GB disk is made and formatted by Windows, with only the UEFI
         Shell and a startup script on it;
      2. it is added to the VM, which starts from it while the screen is saved
         about once a second;
      3. the shell lists the disks the firmware sees and tries to start
         Aurora's GRUB from Aurora's own EFI partition;
      4. the probe disk is removed and the boot order put back.

    Results go to aurora-firmware-test on the Desktop.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\Test-AuroraFirmware.ps1 -Name Aurora
#>
param(
    [string]$Name = "Aurora",
    [string]$Shell = (Join-Path $PSScriptRoot "shellx64.efi"),
    [string]$Out = (Join-Path ([Environment]::GetFolderPath("Desktop")) "aurora-firmware-test"),
    [int]$Seconds = 90
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Run PowerShell as administrator (right-click, Run as administrator)."
}
if (-not (Test-Path $Shell)) { Write-Error "UEFI Shell not found: $Shell" }
Add-Type -AssemblyName System.Drawing

New-Item -ItemType Directory -Force -Path $Out | Out-Null
$verdict = Join-Path $Out "verdict.txt"
"Aurora OS firmware test - $(Get-Date -Format s)" | Set-Content -Encoding UTF8 $verdict
function Say($text) { Write-Host $text; $text | Add-Content -Encoding UTF8 $verdict }

$vm = Get-VM -Name $Name
if ($vm.State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
$auroraDisk = Get-VMHardDiskDrive -VMName $Name | Select-Object -First 1
Say "VM $Name, Aurora's disk $($auroraDisk.Path)"
Say ("Aurora's disk: " + ((Get-VHD -Path $auroraDisk.Path | Select-Object VhdFormat, VhdType, LogicalSectorSize, PhysicalSectorSize, Size, FileSize | Out-String).Trim() -replace "\s+", " "))

# --- 1. the probe disk, made by Windows -----------------------------------------------
$probe = Join-Path $Out "probe.vhdx"
if (Test-Path $probe) { Remove-Item $probe -Force }
New-VHD -Path $probe -SizeBytes 1GB -Dynamic | Out-Null
$disk = Mount-VHD -Path $probe -NoDriveLetter -Passthru | Get-Disk
try {
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT
    # Initialize-Disk adds a Microsoft reserved partition on some versions: not wanted here.
    Get-Partition -DiskNumber $disk.Number -ErrorAction SilentlyContinue |
        Remove-Partition -Confirm:$false -ErrorAction SilentlyContinue
    # An ordinary partition while Windows formats and fills it (it handles those
    # without fuss); it becomes an EFI system partition at the end.
    $part = New-Partition -DiskNumber $disk.Number -UseMaximumSize
    Format-Volume -Partition $part -FileSystem FAT32 -NewFileSystemLabel "PROBE" -Force -Confirm:$false | Out-Null
    $mountPoint = Join-Path $env:TEMP "aurora-probe-esp"
    New-Item -ItemType Directory -Force -Path $mountPoint | Out-Null
    Add-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -AccessPath $mountPoint
    try {
        New-Item -ItemType Directory -Force -Path (Join-Path $mountPoint "EFI\BOOT") | Out-Null
        Copy-Item $Shell (Join-Path $mountPoint "EFI\BOOT\BOOTX64.EFI")
        $script = @(
            "@echo -off",
            'echo "AURORA-PROBE 1: the firmware started the shell from the probe disk"',
            "map",
            "for %i in fs0 fs1 fs2 fs3 fs4",
            "  if exist %i:\EFI\debian\grub.cfg then",
            '    echo "AURORA-PROBE 2: the firmware reads the EFI partition of the Aurora disk as %i"',
            "    ls %i:\EFI\boot",
            '    echo "AURORA-PROBE 3: starting the GRUB of the Aurora disk"',
            "    %i:\EFI\debian\grubx64.efi",
            '    echo "AURORA-PROBE 4: GRUB came back: %lasterror%"',
            "  endif",
            "endfor",
            'echo "AURORA-PROBE 5: end of the script"'
        )
        [IO.File]::WriteAllText((Join-Path $mountPoint "startup.nsh"), (($script -join "`r`n") + "`r`n"), (New-Object Text.ASCIIEncoding))
    } finally {
        Remove-PartitionAccessPath -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -AccessPath $mountPoint -ErrorAction SilentlyContinue
    }
    Set-Partition -DiskNumber $disk.Number -PartitionNumber $part.PartitionNumber -GptType "{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}"
} finally {
    Dismount-VHD -Path $probe
}
Say "Probe disk made: $probe"

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

# --- 2. start from it -------------------------------------------------------------------
$added = $null
try {
    $added = Add-VMHardDiskDrive -VMName $Name -ControllerType SCSI -Path $probe -Passthru
    Set-VMFirmware -VMName $Name -BootOrder $added
    $shots = Join-Path $Out "screens"
    New-Item -ItemType Directory -Force -Path $shots | Out-Null
    $started = Get-Date
    Start-VM -Name $Name
    $n = 0
    $booted = $false
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
    Say ("{0} screens in {1}; an operating system started: {2}" -f $n, $shots, $booted)
} finally {
    # --- 3. put things back ---------------------------------------------------------------
    if ((Get-VM -Name $Name).State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    if ($added) { Remove-VMHardDiskDrive -VMHardDiskDrive $added }
    $order = @(Get-VMDvdDrive -VMName $Name) + @(Get-VMHardDiskDrive -VMName $Name) + @(Get-VMNetworkAdapter -VMName $Name)
    Set-VMFirmware -VMName $Name -BootOrder $order
}
Say "The probe disk is removed and the boot order is DVD, disk, network again."
Say "Folder: $Out"
