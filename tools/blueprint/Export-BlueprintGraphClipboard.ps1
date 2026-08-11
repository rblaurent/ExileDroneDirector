[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [Alias('OutputPath')]
    [string]$DestinationPath,

    [switch]$Force,

    [string]$ExpectedGraph = '',

    [ValidateRange(0, [int]::MaxValue)]
    [int]$ExpectedNodeCount = 0
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
$nodeCount = ([regex]::Matches($normalized, '(?m)^Begin Object Class=')).Count
if ($ExpectedNodeCount -gt 0 -and $nodeCount -ne $ExpectedNodeCount) {
    throw "Blueprint clipboard node count mismatch. Expected $ExpectedNodeCount, found $nodeCount."
}

$graphMatches = [regex]::Matches(
    $normalized,
    'ExportPath="[^"]*:(?<graph>[^.:''"]+)\.[^"]+"'
)
$graphs = @($graphMatches | ForEach-Object { $_.Groups['graph'].Value } | Sort-Object -Unique)
if ($graphs.Count -ne 1) {
    throw "Blueprint clipboard must come from exactly one graph. Found: $($graphs -join ', ')"
}
if ($ExpectedGraph -and $graphs[0] -cne $ExpectedGraph) {
    throw "Blueprint clipboard graph mismatch. Expected '$ExpectedGraph', found '$($graphs[0])'."
}
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
Write-Output "Exported Blueprint graph snippet: $destination ($nodeCount nodes from $($graphs[0]))"
