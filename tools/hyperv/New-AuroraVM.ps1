<#
.SYNOPSIS
    Create a Hyper-V virtual machine for Aurora OS from its ISO, or point an
    existing one at a new ISO.

.DESCRIPTION
    Generation 2 (UEFI), Secure Boot with the "Microsoft UEFI Certificate
    Authority" template (the default Windows template refuses Linux), static
    memory, no checkpoints, the DVD first in the boot order, a 1920x1080 screen
    and enhanced session off (it shows a black window with Aurora).

    If a VM with this name already exists it is kept, disk included: it is
    turned off, its settings are fixed and its DVD drive gets the ISO. Use
    -Recreate to delete it (and its virtual disk) and start over. A disk left
    over from an earlier VM with the same name is reused, or deleted with -Recreate.

    Run it in PowerShell as administrator. See HYPERV.md for the whole guide.

.EXAMPLE
    .\New-AuroraVM.ps1 -IsoPath "$env:USERPROFILE\Desktop\aurora-os-0.1-amd64.iso"

.EXAMPLE
    .\New-AuroraVM.ps1 -IsoPath D:\aurora-os-0.1-amd64.iso -MemoryGB 12 -DiskGB 100 -Recreate
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$IsoPath,
    [string]$Name = "Aurora",
    [int]$MemoryGB = 8,
    [int]$Processors = 4,
    [int]$DiskGB = 60,
    [string]$Folder = "C:\VMs",
    [string]$Switch = "Default Switch",
    [int]$Width = 1920,
    [int]$Height = 1080,
    [switch]$Recreate,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

function Step($text) { Write-Host "==> $text" -ForegroundColor Magenta }

# --- checks -------------------------------------------------------------------

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as administrator (right-click > Run as administrator)."
}
if (-not (Get-Command New-VM -ErrorAction SilentlyContinue)) {
    throw ("Hyper-V is not enabled. Run: Enable-WindowsOptionalFeature -Online " +
           "-FeatureName Microsoft-Hyper-V -All   then restart Windows.")
}
if (-not (Test-Path -LiteralPath $IsoPath -PathType Leaf)) {
    throw "ISO not found: $IsoPath"
}
$iso = (Resolve-Path -LiteralPath $IsoPath).Path
if (-not (Get-VMSwitch -Name $Switch -ErrorAction SilentlyContinue)) {
    $names = (Get-VMSwitch | Select-Object -ExpandProperty Name) -join ", "
    throw "Virtual switch '$Switch' not found. Available: $names. Use -Switch NAME."
}

# --- the VM -------------------------------------------------------------------

$vm = Get-VM -Name $Name -ErrorAction SilentlyContinue

if ($vm -and $Recreate) {
    Step "Deleting the existing VM '$Name' and its virtual disk"
    if ($vm.State -ne "Off") { Stop-VM -Name $Name -TurnOff -Force }
    $disks = Get-VMHardDiskDrive -VMName $Name | Select-Object -ExpandProperty Path
    Remove-VM -Name $Name -Force
    foreach ($d in $disks) { Remove-Item -LiteralPath $d -Force -ErrorAction SilentlyContinue }
    $vm = $null
}

if (-not $vm) {
    New-Item -ItemType Directory -Force -Path $Folder | Out-Null
    $vhd = Join-Path $Folder "$Name.vhdx"
    if ((Test-Path -LiteralPath $vhd) -and $Recreate) {
        Step "Deleting the leftover disk $vhd"
        Remove-Item -LiteralPath $vhd -Force
    }
    if (Test-Path -LiteralPath $vhd) {
        # A disk from an earlier VM with this name (maybe with Aurora installed): keep it.
        Step "Creating '$Name' with the existing disk $vhd (use -Recreate for a new, empty one)"
        New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -Path $Folder `
               -VHDPath $vhd -SwitchName $Switch | Out-Null
    } else {
        Step "Creating '$Name': Generation 2, $MemoryGB GB of memory, $DiskGB GB disk"
        New-VM -Name $Name -Generation 2 -MemoryStartupBytes ($MemoryGB * 1GB) -Path $Folder `
               -NewVHDPath $vhd -NewVHDSizeBytes ($DiskGB * 1GB) -SwitchName $Switch | Out-Null
    }
} else {
    Step "Updating the existing VM '$Name' (its disk is kept)"
    if ($vm.Generation -ne 2) {
        throw "'$Name' is a Generation 1 VM. Run again with -Recreate to replace it."
    }
    if ($vm.State -ne "Off") {
        Step "Turning '$Name' off to change its settings"
        Stop-VM -Name $Name -TurnOff -Force
    }
}

Step "Processors, static memory, no checkpoints"
Set-VM -Name $Name -ProcessorCount $Processors -StaticMemory -MemoryStartupBytes ($MemoryGB * 1GB) `
       -CheckpointType Disabled -AutomaticStopAction ShutDown
try { Set-VM -Name $Name -AutomaticCheckpointsEnabled $false } catch { }  # older Windows lack it

Step "DVD drive with the ISO: $iso"
$dvd = Get-VMDvdDrive -VMName $Name | Select-Object -First 1
if ($dvd) {
    Set-VMDvdDrive -VMName $Name -ControllerNumber $dvd.ControllerNumber `
                   -ControllerLocation $dvd.ControllerLocation -Path $iso
} else {
    Add-VMDvdDrive -VMName $Name -Path $iso
}
$dvd = Get-VMDvdDrive -VMName $Name | Select-Object -First 1

Step "Firmware: Secure Boot for Linux (Microsoft UEFI CA), start from the DVD"
Set-VMFirmware -VMName $Name -EnableSecureBoot On `
               -SecureBootTemplate MicrosoftUEFICertificateAuthority -FirstBootDevice $dvd

Step "Screen ${Width}x${Height}, enhanced session off"
try {
    Set-VMVideo -VMName $Name -HorizontalResolution $Width -VerticalResolution $Height `
                -ResolutionType Single
} catch {
    Write-Warning "Could not set the resolution on this Windows version; change it in Aurora's Settings > Displays."
}
Set-VMHost -EnableEnhancedSessionMode $false

# --- start --------------------------------------------------------------------

Write-Host ""
Write-Host "Aurora OS VM '$Name' is ready." -ForegroundColor Green
Write-Host "  Boot menu: 'Try Aurora OS' for the live desktop; double-click 'Install Aurora OS' to install."
Write-Host "  After installing, remove the ISO:  Set-VMDvdDrive -VMName '$Name' -Path `$null"
Write-Host "  A newer ISO later: run this script again with its path (the installed disk is kept)."

if (-not $NoStart) {
    Step "Starting '$Name' and opening its window"
    Start-VM -Name $Name
    Start-Process -FilePath "vmconnect.exe" -ArgumentList "localhost", "`"$Name`""
}
