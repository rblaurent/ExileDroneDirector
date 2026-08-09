[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SnippetPath,

    [hashtable]$Token = @{},

    [switch]$AllowExternalFunctionEntry,

    [switch]$PassThru
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedSnippet = (Resolve-Path -LiteralPath $SnippetPath).Path
$validator = Join-Path $PSScriptRoot 'Test-BlueprintGraphSnippet.ps1'
& $validator -Path $resolvedSnippet -AllowTokens -AllowExternalFunctionEntry:$AllowExternalFunctionEntry | Write-Verbose

$text = [IO.File]::ReadAllText($resolvedSnippet)
foreach ($key in $Token.Keys) {
    $tokenName = [string]$key
    if ($tokenName -notmatch '^[A-Z][A-Z0-9_]*$') {
        throw "Invalid token name '$tokenName'. Use uppercase letters, digits, and underscores."
    }
    $text = $text.Replace("{{$tokenName}}", [string]$Token[$key])
}

$unresolved = [regex]::Match($text, '\{\{[A-Z][A-Z0-9_]*\}\}')
if ($unresolved.Success) {
    throw "Unresolved Blueprint graph token: $($unresolved.Value)"
}

Set-Clipboard -Value $text
Write-Output "Blueprint graph copied to the Windows clipboard: $resolvedSnippet"

if ($PassThru) {
    Write-Output $text
}
