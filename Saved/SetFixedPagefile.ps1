$ErrorActionPreference = "Stop"

$PagefilePath = "C:\pagefile.sys"
$InitialSizeMB = 40960
$MaximumSizeMB = 49152

$computerSystem = Get-CimInstance -ClassName Win32_ComputerSystem
Set-CimInstance -InputObject $computerSystem -Property @{
    AutomaticManagedPagefile = $false
} | Out-Null

$pagefileSetting = Get-CimInstance -ClassName Win32_PageFileSetting |
    Where-Object { $_.Name -ieq $PagefilePath } |
    Select-Object -First 1

if ($null -eq $pagefileSetting) {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name = $PagefilePath
        InitialSize = $InitialSizeMB
        MaximumSize = $MaximumSizeMB
    } | Out-Null
} else {
    Set-CimInstance -InputObject $pagefileSetting -Property @{
        InitialSize = $InitialSizeMB
        MaximumSize = $MaximumSizeMB
    } | Out-Null
}

$updatedComputerSystem = Get-CimInstance -ClassName Win32_ComputerSystem
$updatedPagefileSetting = Get-CimInstance -ClassName Win32_PageFileSetting |
    Where-Object { $_.Name -ieq $PagefilePath } |
    Select-Object -First 1

if ($updatedComputerSystem.AutomaticManagedPagefile -or
    $null -eq $updatedPagefileSetting -or
    $updatedPagefileSetting.InitialSize -ne $InitialSizeMB -or
    $updatedPagefileSetting.MaximumSize -ne $MaximumSizeMB) {
    throw "Pagefile verification failed."
}
