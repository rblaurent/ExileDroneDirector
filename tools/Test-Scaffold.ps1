[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$RequireMvpAssets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$requiredFiles = @(
    'README.md',
    'project.json',
    'docs\product-design.md',
    'docs\architecture.md',
    'docs\event-system.md',
    'docs\devkit-findings.md',
    'docs\blueprint-workflow.md',
    'docs\visual-design-system.md',
    'docs\implementation-plan.md',
    '.gitattributes',
    '.gitignore',
    'tools\Sync-DevKitContent.ps1',
    'tools\Test-RepositoryBudget.ps1',
    'tools\Invoke-UnrealPython.ps1',
    'tools\unreal\Probe-EnhancedApi.py',
    'tools\unreal\Inspect-BlueprintApi.py',
    'tools\unreal\Inspect-GraphApi.py',
    'tools\unreal\Configure-ClientDirectorVariables.py',
    'tools\unreal\Configure-DroneMovement.py',
    'tools\unreal\Configure-WaypointCapture.py',
    'tools\unreal\Configure-WaypointDocumentBridge.py',
    'tools\unreal\Configure-WaypointStructSync.py',
    'tools\unreal\Configure-FlypathDocumentBridge.py',
    'tools\unreal\Configure-DocumentSync.py',
    'tools\unreal\Configure-PathPreview.py',
    'tools\unreal\Configure-LinearPlayback.py',
    'tools\unreal\Probe-WaypointTypes.py',
    'tools\unreal\Validate-WaypointCapturePIE.py',
    'tools\unreal\Validate-WaypointStructSyncPIE.py',
    'tools\unreal\Validate-DocumentSyncPIE.py',
    'tools\unreal\Validate-LinearPlaybackPIE.py',
    'tools\unreal\Validate-PathPreviewMarkersPIE.py',
    'tools\playback\linear_reference.py',
    'tools\playback\test_linear_reference.py',
    'tools\preview\linear_preview.py',
    'tools\preview\test_linear_preview.py',
    'tools\document\flypath_document.py',
    'tools\document\test_flypath_document.py',
    'tools\document\waypoint_bridge.py',
    'tools\document\test_waypoint_bridge.py',
    'tools\document\blueprint_v1_schema.json',
    'tools\document\test_blueprint_v1_schema.py',
    'tools\document\document_bridge.py',
    'tools\document\test_document_bridge.py',
    'tools\unreal\Generate-MvpScaffold.py',
    'tools\blueprint\Export-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Set-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Test-BlueprintGraphSnippet.ps1',
    'tools\blueprint\Test-BlueprintGraphContracts.ps1',
    'tools\blueprint\Build-RollInputGraph.py',
    'tools\blueprint\templates\horizon-node-forms.eddgraph',
    'tools\blueprint\Build-ClientRollDispatch.py',
    'tools\blueprint\Build-ClientWaypointDispatch.py',
    'tools\blueprint\Build-ClientWaypointEditDispatch.py',
    'tools\blueprint\Build-WaypointCaptureGraph.py',
    'tools\blueprint\Build-WaypointStructSyncGraph.py',
    'tools\blueprint\Build-DocumentSyncGraph.py',
    'tools\blueprint\Test-DocumentSyncStructForms.py',
    'tools\blueprint\Test-DocumentSyncContracts.py',
    'tools\blueprint\Build-WaypointEditGraphs.py',
    'tools\blueprint\Build-WaypointFeedbackDispatch.py',
    'tools\blueprint\Build-LinearPlaybackGraphs.py',
    'tools\blueprint\Build-LinearPlaybackDispatch.py',
    'tools\blueprint\Test-WaypointCaptureContracts.py',
    'tools\blueprint\Test-WaypointStructSyncContracts.py',
    'tools\blueprint\Test-WaypointEditContracts.py',
    'tools\blueprint\Test-WaypointFeedbackContracts.py',
    'tools\blueprint\Test-LinearPlaybackContracts.py',
    'tools\blueprint\Test-LinearPlaybackDispatchContracts.py',
    'tools\blueprint\Test-PathPreviewContracts.py',
    'tools\blueprint\Build-PathPreviewMarkerGraph.py',
    'tools\blueprint\templates\waypoint-capture-node-forms.eddgraph',
    'tools\blueprint\templates\waypoint-struct-sync-node-forms.eddgraph',
    'tools\blueprint\templates\document-sync-struct-node-forms.eddgraph',
    'tools\blueprint\templates\waypoint-edit-node-forms.eddgraph',
    'tools\blueprint\templates\linear-playback-node-forms.eddgraph',
    'tools\blueprint\templates\path-preview-marker-node-forms.eddgraph',
    'tools\blueprint\snippets\toggle-input.eddgraph',
    'tools\blueprint\snippets\toggle-state.eddgraph',
    'tools\blueprint\snippets\enter-drone-mode.eddgraph',
    'tools\blueprint\snippets\place-drone-at-current-view.eddgraph',
    'tools\blueprint\snippets\activate-drone-view.eddgraph',
    'tools\blueprint\snippets\switch-to-drone-view.eddgraph',
    'tools\blueprint\snippets\exit-drone-mode.eddgraph',
    'tools\blueprint\snippets\emergency-exit-drone-mode.eddgraph',
    'tools\blueprint\snippets\client-director-event-graph.eddgraph',
    'tools\blueprint\snippets\capture-current-waypoint.eddgraph',
    'tools\blueprint\snippets\sync-draft-waypoints-v1.eddgraph',
    'tools\blueprint\snippets\replace-selected-waypoint.eddgraph',
    'tools\blueprint\snippets\delete-selected-waypoint.eddgraph',
    'tools\blueprint\snippets\start-linear-playback.eddgraph',
    'tools\blueprint\snippets\update-linear-playback.eddgraph',
    'tools\blueprint\snippets\stop-linear-playback.eddgraph',
    'tools\blueprint\snippets\apply-translation-input.eddgraph',
    'tools\blueprint\snippets\apply-rotation-input.eddgraph',
    'tools\blueprint\snippets\apply-roll-and-horizon-input.eddgraph',
    'tools\blueprint\snippets\update-speed-controls.eddgraph',
    'tools\blueprint\snippets\drone-camera-event-graph.eddgraph',
    'tools\blueprint\snippets\cache-original-pawn.eddgraph',
    'tools\blueprint\snippets\possess-drone-camera.eddgraph',
    'tools\blueprint\snippets\restore-original-possession.eddgraph',
    'tools\blueprint\snippets\clear-path-preview-v1.eddgraph',
    'tools\blueprint\snippets\rebuild-path-preview-markers-v1.eddgraph'
)

$missing = @(
    $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
    }
)

if ($missing.Count -gt 0) {
    throw "Missing scaffold files: $($missing -join ', ')"
}

$manifestPath = Join-Path $ProjectRoot 'project.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.modFolder -ne 'ExileDroneDirector') {
    throw "Unexpected modFolder in project.json: $($manifest.modFolder)"
}

$movementConfigPath = Join-Path $ProjectRoot 'tools\unreal\Configure-DroneMovement.py'
$movementConfig = [IO.File]::ReadAllText($movementConfigPath)
$expectedMovementDefaults = [ordered]@{
    BaseMoveSpeed = '600.0'
    CruiseMoveSpeed = '600.0'
    CurrentMoveSpeed = '600.0'
    BoostMultiplier = '3.0'
    PrecisionMultiplier = '0.25'
    SpeedTrimRatio = '1.25'
    MinMoveSpeed = '30.0'
    MaxMoveSpeed = '6000.0'
    SpeedResponse = '6.0'
    LookSensitivity = '0.12'
    ManualRollSpeed = '90.0'
    CurrentRollSpeed = '0.0'
    RollInputResponse = '8.0'
    HorizonLockResponse = '4.0'
}
foreach ($entry in $expectedMovementDefaults.GetEnumerator()) {
    $pattern = '"{0}"\s*:\s*{1}' -f [regex]::Escape($entry.Key), [regex]::Escape($entry.Value)
    if ($movementConfig -notmatch $pattern) {
        throw "Missing movement default contract: $($entry.Key)=$($entry.Value)"
    }
}
foreach ($functionName in @('ApplyTranslationInput', 'ApplyRotationInput', 'UpdateSpeedControls', 'ApplyRollAndHorizonInput')) {
    if ($movementConfig -notmatch ('"{0}"' -f [regex]::Escape($functionName))) {
        throw "Missing movement function contract: $functionName"
    }
}
if ($movementConfig -notmatch '"HorizonLockEnabled"\s*:\s*True') {
    throw 'Missing movement default contract: HorizonLockEnabled=True'
}
$trimRatio = [double]$expectedMovementDefaults.SpeedTrimRatio
$trimUp = [Math]::Exp([Math]::Log($trimRatio))
$trimDown = [Math]::Exp(-[Math]::Log($trimRatio))
if ([Math]::Abs(($trimUp * $trimDown) - 1.0) -gt 0.000000001) {
    throw 'SpeedTrimRatio must yield reciprocal positive and negative steps.'
}

$contentRoot = Join-Path $ProjectRoot "DevKitContent\$($manifest.modFolder)"
if (-not (Test-Path -LiteralPath $contentRoot -PathType Container)) {
    throw "Missing DevKit content mirror: $contentRoot"
}

if ($RequireMvpAssets) {
    $missingAssets = @(
        $manifest.mvpAssets | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $contentRoot $_) -PathType Leaf)
        }
    )
    if ($missingAssets.Count -gt 0) {
        throw "Missing MVP assets: $($missingAssets -join ', ')"
    }
}

Write-Output "Scaffold valid: $($manifest.name) $($manifest.version)"
Write-Output "Content mirror: $contentRoot"
if (-not $RequireMvpAssets) {
    Write-Output 'MVP asset presence was not required for this pre-DevKit validation.'
}

& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphContracts.ps1') `
    -ProjectRoot $ProjectRoot

$scratchRoot = if ($env:REDLEAF_SCRATCH_DIR) {
    $env:REDLEAF_SCRATCH_DIR
} else {
    [IO.Path]::GetTempPath()
}
$syncNonce = [guid]::NewGuid().ToString('N')
$generatedSync = Join-Path $scratchRoot "edd-sync-$syncNonce.eddgraph"
$generatedSyncPaste = Join-Path $scratchRoot "edd-sync-$syncNonce-paste.eddgraph"
$checkedSync = Join-Path $ProjectRoot 'tools\blueprint\snippets\sync-draft-waypoints-v1.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-WaypointStructSyncGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedSync `
    --paste-output $generatedSyncPaste
if ($LASTEXITCODE -ne 0) {
    throw "Waypoint struct sync generation failed with exit code $LASTEXITCODE."
}
if ((Get-FileHash -Algorithm SHA256 $generatedSync).Hash -ne (Get-FileHash -Algorithm SHA256 $checkedSync).Hash) {
    throw 'Checked waypoint struct sync graph has drifted from its deterministic generator.'
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-WaypointStructSyncContracts.py') `
    --graph $generatedSync `
    --paste-graph $generatedSyncPaste
if ($LASTEXITCODE -ne 0) {
    throw "Generated waypoint struct sync contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\playback\test_linear_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Linear playback reference contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\preview\test_linear_preview.py')
if ($LASTEXITCODE -ne 0) {
    throw "Linear path-preview contracts failed with exit code $LASTEXITCODE."
}

$pathPreviewNonce = [guid]::NewGuid().ToString('N')
$generatedPathPreview = Join-Path $scratchRoot "edd-path-preview-$pathPreviewNonce.eddgraph"
$generatedPathPreviewPaste = Join-Path $scratchRoot "edd-path-preview-$pathPreviewNonce-paste.eddgraph"
$generatedPathPreviewRepeat = Join-Path $scratchRoot "edd-path-preview-$pathPreviewNonce-repeat.eddgraph"
$generatedPathPreviewRepeatPaste = Join-Path $scratchRoot "edd-path-preview-$pathPreviewNonce-repeat-paste.eddgraph"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewMarkerGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedPathPreview `
    --paste-output $generatedPathPreviewPaste
if ($LASTEXITCODE -ne 0) {
    throw "Path-preview marker graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewMarkerGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedPathPreviewRepeat `
    --paste-output $generatedPathPreviewRepeatPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repeated path-preview marker graph generation failed with exit code $LASTEXITCODE."
}
if ((Get-FileHash -Algorithm SHA256 $generatedPathPreview).Hash -ne (Get-FileHash -Algorithm SHA256 $generatedPathPreviewRepeat).Hash) {
    throw 'Path-preview marker full-graph generation is not deterministic.'
}
if ((Get-FileHash -Algorithm SHA256 $generatedPathPreviewPaste).Hash -ne (Get-FileHash -Algorithm SHA256 $generatedPathPreviewRepeatPaste).Hash) {
    throw 'Path-preview marker paste-graph generation is not deterministic.'
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedPathPreview
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedPathPreviewPaste
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewContracts.py') `
    --clear (Join-Path $ProjectRoot 'tools\blueprint\snippets\clear-path-preview-v1.eddgraph') `
    --rebuild $generatedPathPreview
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview marker contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_flypath_document.py')
if ($LASTEXITCODE -ne 0) {
    throw "Flypath document contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_waypoint_bridge.py')
if ($LASTEXITCODE -ne 0) {
    throw "Waypoint bridge contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_blueprint_v1_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Blueprint version-1 schema contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_document_bridge.py')
if ($LASTEXITCODE -ne 0) {
    throw "Typed document bridge contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DocumentSyncStructForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\document-sync-struct-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Document sync native struct-form contracts failed with exit code $LASTEXITCODE."
}

$documentSyncNonce = [guid]::NewGuid().ToString('N')
$generatedDocumentSync = Join-Path $scratchRoot "edd-document-sync-$documentSyncNonce.eddgraph"
$generatedDocumentSyncPaste = Join-Path $scratchRoot "edd-document-sync-$documentSyncNonce-paste.eddgraph"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DocumentSyncGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedDocumentSync `
    --paste-output $generatedDocumentSyncPaste
if ($LASTEXITCODE -ne 0) {
    throw "Document sync graph generation failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedDocumentSync
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedDocumentSyncPaste
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DocumentSyncContracts.py') `
    --project-root $ProjectRoot `
    --graph $generatedDocumentSync `
    --paste-graph $generatedDocumentSyncPaste
if ($LASTEXITCODE -ne 0) {
    throw "Document sync graph contracts failed with exit code $LASTEXITCODE."
}
