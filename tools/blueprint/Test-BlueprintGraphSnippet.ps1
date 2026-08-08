[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
    [string[]]$Path,

    [switch]$AllowTokens
)

begin {
    Set-StrictMode -Version Latest
    $ErrorActionPreference = 'Stop'
}

process {
    foreach ($inputPath in $Path) {
        $resolvedPath = (Resolve-Path -LiteralPath $inputPath).Path
        $text = [IO.File]::ReadAllText($resolvedPath)

        if ([string]::IsNullOrWhiteSpace($text)) {
            throw "Blueprint graph snippet is empty: $resolvedPath"
        }

        $beginMatches = [regex]::Matches(
            $text,
            '(?m)^Begin Object Class=(?<Class>\S+) Name="(?<Name>[^"]+)"'
        )
        $endMatches = [regex]::Matches($text, '(?m)^End Object\s*$')

        if ($beginMatches.Count -eq 0) {
            throw "No Blueprint graph nodes were found in: $resolvedPath"
        }
        if ($beginMatches.Count -ne $endMatches.Count) {
            throw "Unbalanced Begin/End Object records in $resolvedPath ($($beginMatches.Count) begin, $($endMatches.Count) end)."
        }

        $nodeNames = @($beginMatches | ForEach-Object { $_.Groups['Name'].Value })
        $duplicateNames = @($nodeNames | Group-Object | Where-Object Count -gt 1)
        if ($duplicateNames.Count -gt 0) {
            throw "Duplicate node names in $resolvedPath`: $($duplicateNames.Name -join ', ')"
        }

        $invalidClasses = @(
            $beginMatches |
                ForEach-Object { $_.Groups['Class'].Value } |
                Where-Object { $_ -notmatch '^/Script/BlueprintGraph\.' } |
                Select-Object -Unique
        )
        if ($invalidClasses.Count -gt 0) {
            throw "Non-BlueprintGraph node classes in $resolvedPath`: $($invalidClasses -join ', ')"
        }

        $foreignExports = @(
            [regex]::Matches($text, 'ExportPath="[^"]*''(?<Path>/Game/[^"]+)"') |
                ForEach-Object { $_.Groups['Path'].Value } |
                Where-Object { $_ -notlike '/Game/Mods/ExileDroneDirector/*' } |
                Select-Object -Unique
        )
        if ($foreignExports.Count -gt 0) {
            throw "Snippet exports nodes from outside the mod namespace: $($foreignExports -join ', ')"
        }

        foreach ($identifierKind in @('NodeGuid', 'PinId')) {
            $pattern = if ($identifierKind -eq 'NodeGuid') {
                '(?m)^\s*NodeGuid=(?<Id>[0-9A-F]{32})\s*$'
            }
            else {
                'CustomProperties Pin \(PinId=(?<Id>[0-9A-F]{32})'
            }
            $identifiers = @(
                [regex]::Matches($text, $pattern) |
                    ForEach-Object { $_.Groups['Id'].Value }
            )
            $duplicates = @($identifiers | Group-Object | Where-Object Count -gt 1)
            if ($duplicates.Count -gt 0) {
                throw "Duplicate $identifierKind values in $resolvedPath`: $($duplicates.Name -join ', ')"
            }
        }

        $linkedNodeNames = @(
            [regex]::Matches($text, 'LinkedTo=\((?<Name>K2Node_[A-Za-z0-9_]+)\s+[0-9A-F]{32}') |
                ForEach-Object { $_.Groups['Name'].Value } |
                Select-Object -Unique
        )
        $unknownLinks = @($linkedNodeNames | Where-Object { $_ -notin $nodeNames })
        if ($unknownLinks.Count -gt 0) {
            throw "LinkedTo references unknown nodes in $resolvedPath`: $($unknownLinks -join ', ')"
        }

        if (-not $AllowTokens -and $text -match '\{\{[A-Z][A-Z0-9_]*\}\}') {
            throw "Unresolved template token '$($Matches[0])' in $resolvedPath."
        }

        $pinCount = [regex]::Matches($text, 'CustomProperties Pin \(PinId=').Count
        Write-Output "Blueprint graph snippet valid: $resolvedPath ($($beginMatches.Count) nodes, $pinCount pins)"
    }
}
