[CmdletBinding()]
param(
    [string]$DevKitRoot = 'F:\CEUE5Devkit'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot 'unreal\Validate-ColdAssetLoad.py'
& (Join-Path $PSScriptRoot 'Invoke-UnrealPython.ps1') `
    -ScriptPath $scriptPath `
    -DevKitRoot $DevKitRoot

if ($LASTEXITCODE -ne 0) {
    throw "Cold asset-load validation failed with exit code $LASTEXITCODE."
}
