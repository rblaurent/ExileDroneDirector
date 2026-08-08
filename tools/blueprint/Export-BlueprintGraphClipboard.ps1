[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationPath,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$clipboardText = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($clipboardText)) {
    throw 'The Windows clipboard is empty.'
}
if (-not $clipboardText.StartsWith('Begin Object Class=/Script/BlueprintGraph.')) {
    throw 'The Windows clipboard does not contain Unreal Blueprint graph nodes.'
}

$destination = [IO.Path]::GetFullPath($DestinationPath)
if ((Test-Path -LiteralPath $destination) -and -not $Force) {
    throw "Destination already exists. Pass -Force to replace it: $destination"
}

$normalized = $clipboardText.Replace("`r`n", "`n").TrimEnd() + "`n"
$temporaryPath = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllText($temporaryPath, $normalized, [Text.UTF8Encoding]::new($false))
    $validator = Join-Path $PSScriptRoot 'Test-BlueprintGraphSnippet.ps1'
    & $validator -Path $temporaryPath | Write-Verbose
}
finally {
    Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
}

$parent = Split-Path -Parent $destination
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
[IO.File]::WriteAllText($destination, $normalized, [Text.UTF8Encoding]::new($false))
Write-Output "Exported Blueprint graph snippet: $destination"
