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
    'tools\Test-RepositorySaveGame.ps1',
    'tools\Test-RepositoryService.ps1',
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
    'tools\unreal\Configure-PathPreviewLifecycle.py',
    'tools\unreal\Configure-DraftHistory.py',
    'tools\unreal\Configure-CleanFrame.py',
    'tools\unreal\Configure-LinearPlayback.py',
    'tools\unreal\Probe-WaypointTypes.py',
    'tools\unreal\Probe-PathPreviewLifecycleTypes.py',
    'tools\unreal\Validate-WaypointCapturePIE.py',
    'tools\unreal\Validate-WaypointStructSyncPIE.py',
    'tools\unreal\Validate-DocumentSyncPIE.py',
    'tools\unreal\Validate-LinearPlaybackPIE.py',
    'tools\unreal\Validate-PathPreviewMarkersPIE.py',
    'tools\unreal\Validate-PathPreviewSegmentsPIE.py',
    'tools\unreal\Validate-PathPreviewLifecyclePIE.py',
    'tools\unreal\Validate-CleanFramePIE.py',
    'tools\unreal\Validate-DraftHistoryShortcutsPIE.py',
    'tools\unreal\Configure-RepositorySaveGame.py',
    'tools\unreal\Write-RepositorySaveGameProbe.py',
    'tools\unreal\Read-RepositorySaveGameProbe.py',
    'tools\unreal\Configure-RepositoryService.py',
    'tools\unreal\Open-RepositoryServiceEditor.py',
    'tools\unreal\Validate-RepositoryJsonCodec.py',
    'tools\unreal\Probe-HashEncodingApi.py',
    'tools\unreal\Prepare-RepositoryJsonNodeProbe.py',
    'tools\unreal\Inspect-RepositoryJsonBlueprintApi.py',
    'tools\unreal\Inspect-QuaternionBlueprintApi.py',
    'tools\unreal\Delete-RepositoryJsonNodeProbe.py',
    'tools\playback\linear_reference.py',
    'tools\playback\test_linear_reference.py',
    'tools\preview\linear_preview.py',
    'tools\preview\test_linear_preview.py',
    'tools\history\draft_history.py',
    'tools\history\test_draft_history.py',
    'tools\document\flypath_document.py',
    'tools\document\test_flypath_document.py',
    'tools\document\flypath_repository.py',
    'tools\document\test_flypath_repository.py',
    'tools\document\waypoint_bridge.py',
    'tools\document\test_waypoint_bridge.py',
    'tools\document\blueprint_v1_schema.json',
    'tools\document\test_blueprint_v1_schema.py',
    'tools\document\document_bridge.py',
    'tools\document\test_document_bridge.py',
    'tools\persistence\repository_savegame_schema.json',
    'tools\persistence\test_repository_savegame_schema.py',
    'tools\repository\blueprint_repository_service_schema.json',
    'tools\repository\test_blueprint_repository_service_schema.py',
    'tools\blueprint\Build-RepositoryCoreGraphs.py',
    'tools\blueprint\Build-RepositoryJsonMissingNodeProbe.py',
    'tools\blueprint\Test-RepositoryJsonNodeForms.py',
    'tools\blueprint\Test-RepositoryCodecMathNodeForms.py',
    'tools\blueprint\Test-RepositoryCoreContracts.py',
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
    'tools\blueprint\Build-PathPreviewSegmentGraph.py',
    'tools\blueprint\Build-PathPreviewLifecycleGraphs.py',
    'tools\blueprint\Build-PathPreviewIntegrationGraphs.py',
    'tools\blueprint\Test-PathPreviewLifecycleContracts.py',
    'tools\blueprint\Test-PathPreviewIntegrationContracts.py',
    'tools\blueprint\Build-DraftHistoryGraphs.py',
    'tools\blueprint\Test-DraftHistoryContracts.py',
    'tools\blueprint\Build-DraftHistoryIntegrationGraphs.py',
    'tools\blueprint\Test-DraftHistoryIntegrationContracts.py',
    'tools\blueprint\Build-MutationDiagnosticGraphs.py',
    'tools\blueprint\Test-MutationDiagnosticContracts.py',
    'tools\blueprint\Build-DraftHistoryDispatch.py',
    'tools\blueprint\Test-DraftHistoryDispatchContracts.py',
    'tools\blueprint\Build-CleanFrameGraphs.py',
    'tools\blueprint\Test-CleanFrameContracts.py',
    'tools\blueprint\Build-CleanFrameIntegrationGraphs.py',
    'tools\blueprint\Test-CleanFrameIntegrationContracts.py',
    'tools\blueprint\templates\waypoint-capture-node-forms.eddgraph',
    'tools\blueprint\templates\waypoint-struct-sync-node-forms.eddgraph',
    'tools\blueprint\templates\document-sync-struct-node-forms.eddgraph',
    'tools\blueprint\templates\waypoint-edit-node-forms.eddgraph',
    'tools\blueprint\templates\linear-playback-node-forms.eddgraph',
    'tools\blueprint\templates\path-preview-marker-node-forms.eddgraph',
    'tools\blueprint\templates\path-preview-segment-node-forms.eddgraph',
    'tools\blueprint\templates\conan-clean-frame-node-forms.eddgraph',
    'tools\blueprint\templates\repository-json-node-forms.eddgraph',
    'tools\blueprint\templates\repository-codec-math-node-forms.eddgraph',
    'tools\blueprint\snippets\toggle-input.eddgraph',
    'tools\blueprint\snippets\toggle-state.eddgraph',
    'tools\blueprint\snippets\enter-drone-mode.eddgraph',
    'tools\blueprint\snippets\place-drone-at-current-view.eddgraph',
    'tools\blueprint\snippets\activate-drone-view.eddgraph',
    'tools\blueprint\snippets\switch-to-drone-view.eddgraph',
    'tools\blueprint\snippets\exit-drone-mode.eddgraph',
    'tools\blueprint\snippets\emergency-exit-drone-mode.eddgraph',
    'tools\blueprint\snippets\client-director-event-graph.eddgraph',
    'tools\blueprint\snippets\client-director-event-playback-v1.eddgraph',
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
    'tools\blueprint\snippets\reset-repository-result-v1.eddgraph',
    'tools\blueprint\snippets\reset-repository-result-v1-paste.eddgraph',
    'tools\blueprint\snippets\find-record-index-v1.eddgraph',
    'tools\blueprint\snippets\find-record-index-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-repository-result-v1.eddgraph',
    'tools\blueprint\live-snippets\find-record-index-v1.eddgraph',
    'tools\blueprint\snippets\cache-original-pawn.eddgraph',
    'tools\blueprint\snippets\possess-drone-camera.eddgraph',
    'tools\blueprint\snippets\restore-original-possession.eddgraph',
    'tools\blueprint\snippets\clear-path-preview-v1.eddgraph',
    'tools\blueprint\snippets\rebuild-path-preview-markers-v1.eddgraph',
    'tools\blueprint\snippets\rebuild-path-preview-segments-v1.eddgraph',
    'tools\blueprint\snippets\refresh-path-preview-v1.eddgraph',
    'tools\blueprint\snippets\destroy-path-preview-v1.eddgraph',
    'tools\blueprint\snippets\enter-drone-mode-preview.eddgraph',
    'tools\blueprint\snippets\exit-drone-mode-preview.eddgraph',
    'tools\blueprint\snippets\capture-current-waypoint-preview.eddgraph',
    'tools\blueprint\snippets\replace-selected-waypoint-preview.eddgraph',
    'tools\blueprint\snippets\delete-selected-waypoint-preview.eddgraph',
    'tools\blueprint\snippets\push-current-to-undo-v1.eddgraph',
    'tools\blueprint\snippets\push-current-to-redo-v1.eddgraph',
    'tools\blueprint\snippets\record-undo-snapshot-v1.eddgraph',
    'tools\blueprint\snippets\apply-history-snapshot-v1.eddgraph',
    'tools\blueprint\snippets\undo-draft-v1.eddgraph',
    'tools\blueprint\snippets\redo-draft-v1.eddgraph',
    'tools\blueprint\snippets\capture-current-waypoint-history-v1.eddgraph',
    'tools\blueprint\snippets\replace-selected-waypoint-history-v1.eddgraph',
    'tools\blueprint\snippets\delete-selected-waypoint-history-v1.eddgraph',
    'tools\blueprint\snippets\capture-current-waypoint-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\replace-selected-waypoint-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\delete-selected-waypoint-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\enter-clean-frame-v1.eddgraph',
    'tools\blueprint\snippets\exit-clean-frame-v1.eddgraph',
    'tools\blueprint\snippets\toggle-clean-frame-v1.eddgraph',
    'tools\blueprint\snippets\exit-drone-mode-clean-frame.eddgraph',
    'tools\blueprint\snippets\client-director-event-graph-clean-frame.eddgraph'
)

$missing = @(
    $requiredFiles | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $ProjectRoot $_) -PathType Leaf)
    }
)

if ($missing.Count -gt 0) {
    throw "Missing scaffold files: $($missing -join ', ')"
}

foreach ($pythonFile in Get-ChildItem -LiteralPath (Join-Path $ProjectRoot 'tools') -Recurse -Filter '*.py' -File) {
    & python -c "import ast,pathlib,sys; p=pathlib.Path(sys.argv[1]); ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))" $pythonFile.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Python syntax validation failed: $($pythonFile.FullName)"
    }
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

$pathPreviewSegmentNonce = [guid]::NewGuid().ToString('N')
$generatedPathPreviewSegments = Join-Path $scratchRoot "edd-path-preview-segments-$pathPreviewSegmentNonce.eddgraph"
$generatedPathPreviewSegmentsPaste = Join-Path $scratchRoot "edd-path-preview-segments-$pathPreviewSegmentNonce-paste.eddgraph"
$generatedPathPreviewSegmentsRepeat = Join-Path $scratchRoot "edd-path-preview-segments-$pathPreviewSegmentNonce-repeat.eddgraph"
$generatedPathPreviewSegmentsRepeatPaste = Join-Path $scratchRoot "edd-path-preview-segments-$pathPreviewSegmentNonce-repeat-paste.eddgraph"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewSegmentGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedPathPreviewSegments `
    --paste-output $generatedPathPreviewSegmentsPaste
if ($LASTEXITCODE -ne 0) {
    throw "Path-preview segment graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewSegmentGraph.py') `
    --project-root $ProjectRoot `
    --output $generatedPathPreviewSegmentsRepeat `
    --paste-output $generatedPathPreviewSegmentsRepeatPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repeated path-preview segment graph generation failed with exit code $LASTEXITCODE."
}
if ((Get-FileHash -Algorithm SHA256 $generatedPathPreviewSegments).Hash -ne (Get-FileHash -Algorithm SHA256 $generatedPathPreviewSegmentsRepeat).Hash) {
    throw 'Path-preview segment full-graph generation is not deterministic.'
}
if ((Get-FileHash -Algorithm SHA256 $generatedPathPreviewSegmentsPaste).Hash -ne (Get-FileHash -Algorithm SHA256 $generatedPathPreviewSegmentsRepeatPaste).Hash) {
    throw 'Path-preview segment paste-graph generation is not deterministic.'
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedPathPreviewSegments
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $generatedPathPreviewSegmentsPaste
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewContracts.py') `
    --clear (Join-Path $ProjectRoot 'tools\blueprint\snippets\clear-path-preview-v1.eddgraph') `
    --segments $generatedPathPreviewSegments
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview segment contracts failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path (Join-Path $ProjectRoot 'tools\blueprint\snippets\rebuild-path-preview-segments-v1.eddgraph')
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewContracts.py') `
    --clear (Join-Path $ProjectRoot 'tools\blueprint\snippets\clear-path-preview-v1.eddgraph') `
    --segments (Join-Path $ProjectRoot 'tools\blueprint\snippets\rebuild-path-preview-segments-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Checked path-preview segment contracts failed with exit code $LASTEXITCODE."
}

$pathPreviewLifecycleNonce = [guid]::NewGuid().ToString('N')
$generatedRefresh = Join-Path $scratchRoot "edd-preview-refresh-$pathPreviewLifecycleNonce.eddgraph"
$generatedRefreshPaste = Join-Path $scratchRoot "edd-preview-refresh-$pathPreviewLifecycleNonce-paste.eddgraph"
$generatedDestroy = Join-Path $scratchRoot "edd-preview-destroy-$pathPreviewLifecycleNonce.eddgraph"
$generatedDestroyPaste = Join-Path $scratchRoot "edd-preview-destroy-$pathPreviewLifecycleNonce-paste.eddgraph"
$generatedRefreshRepeat = Join-Path $scratchRoot "edd-preview-refresh-$pathPreviewLifecycleNonce-repeat.eddgraph"
$generatedRefreshRepeatPaste = Join-Path $scratchRoot "edd-preview-refresh-$pathPreviewLifecycleNonce-repeat-paste.eddgraph"
$generatedDestroyRepeat = Join-Path $scratchRoot "edd-preview-destroy-$pathPreviewLifecycleNonce-repeat.eddgraph"
$generatedDestroyRepeatPaste = Join-Path $scratchRoot "edd-preview-destroy-$pathPreviewLifecycleNonce-repeat-paste.eddgraph"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewLifecycleGraphs.py') `
    --project-root $ProjectRoot `
    --refresh-output $generatedRefresh `
    --refresh-paste-output $generatedRefreshPaste `
    --destroy-output $generatedDestroy `
    --destroy-paste-output $generatedDestroyPaste
if ($LASTEXITCODE -ne 0) {
    throw "Path-preview lifecycle graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewLifecycleGraphs.py') `
    --project-root $ProjectRoot `
    --refresh-output $generatedRefreshRepeat `
    --refresh-paste-output $generatedRefreshRepeatPaste `
    --destroy-output $generatedDestroyRepeat `
    --destroy-paste-output $generatedDestroyRepeatPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repeated path-preview lifecycle graph generation failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @($generatedRefresh, $generatedRefreshRepeat),
    @($generatedRefreshPaste, $generatedRefreshRepeatPaste),
    @($generatedDestroy, $generatedDestroyRepeat),
    @($generatedDestroyPaste, $generatedDestroyRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Path-preview lifecycle graph generation is not deterministic: $($pair[0])"
    }
}
foreach ($graph in @($generatedRefresh, $generatedRefreshPaste, $generatedDestroy, $generatedDestroyPaste)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewLifecycleContracts.py') `
    --project-root $ProjectRoot --refresh $generatedRefresh --destroy $generatedDestroy
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview lifecycle contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewLifecycleContracts.py') `
    --project-root $ProjectRoot --refresh $generatedRefreshPaste --destroy $generatedDestroyPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview lifecycle paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewLifecycleContracts.py') `
    --project-root $ProjectRoot `
    --refresh (Join-Path $ProjectRoot 'tools\blueprint\snippets\refresh-path-preview-v1.eddgraph') `
    --destroy (Join-Path $ProjectRoot 'tools\blueprint\snippets\destroy-path-preview-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Checked path-preview lifecycle contracts failed with exit code $LASTEXITCODE."
}

$pathPreviewIntegrationNonce = [guid]::NewGuid().ToString('N')
$generatedIntegrationDir = Join-Path $scratchRoot "edd-preview-integration-$pathPreviewIntegrationNonce"
$generatedIntegrationRepeatDir = Join-Path $scratchRoot "edd-preview-integration-$pathPreviewIntegrationNonce-repeat"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewIntegrationGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedIntegrationDir
if ($LASTEXITCODE -ne 0) {
    throw "Path-preview integration graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-PathPreviewIntegrationGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedIntegrationRepeatDir
if ($LASTEXITCODE -ne 0) {
    throw "Repeated path-preview integration graph generation failed with exit code $LASTEXITCODE."
}
$integrationFiles = @(
    'enter-drone-mode-preview.eddgraph',
    'enter-drone-mode-preview-paste.eddgraph',
    'exit-drone-mode-preview.eddgraph',
    'exit-drone-mode-preview-paste.eddgraph',
    'capture-current-waypoint-preview.eddgraph',
    'capture-current-waypoint-preview-paste.eddgraph',
    'replace-selected-waypoint-preview.eddgraph',
    'replace-selected-waypoint-preview-paste.eddgraph',
    'delete-selected-waypoint-preview.eddgraph',
    'delete-selected-waypoint-preview-paste.eddgraph'
)
foreach ($file in $integrationFiles) {
    $first = Join-Path $generatedIntegrationDir $file
    $second = Join-Path $generatedIntegrationRepeatDir $file
    if ((Get-FileHash -Algorithm SHA256 $first).Hash -ne (Get-FileHash -Algorithm SHA256 $second).Hash) {
        throw "Path-preview integration graph generation is not deterministic: $file"
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $first
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedIntegrationDir
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview integration contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedIntegrationDir --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated path-preview integration paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-PathPreviewIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir (Join-Path $ProjectRoot 'tools\blueprint\snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Checked path-preview integration contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_flypath_document.py')
if ($LASTEXITCODE -ne 0) {
    throw "Flypath document contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\document\test_flypath_repository.py')
if ($LASTEXITCODE -ne 0) {
    throw "Flypath repository contracts failed with exit code $LASTEXITCODE."
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

& python (Join-Path $ProjectRoot 'tools\persistence\test_repository_savegame_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame schema contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\repository\test_blueprint_repository_service_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Blueprint repository service schema contracts failed with exit code $LASTEXITCODE."
}

& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryJsonNodeForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-json-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository JSON native node-form contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCodecMathNodeForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-codec-math-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository codec quaternion node-form contracts failed with exit code $LASTEXITCODE."
}

$repositoryCoreNonce = [guid]::NewGuid().ToString('N')
$repositoryCoreRoot = Join-Path $scratchRoot "edd-repository-core-$repositoryCoreNonce"
$repositoryCoreFull = Join-Path $repositoryCoreRoot 'full'
$repositoryCorePaste = Join-Path $repositoryCoreRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryCoreFull, $repositoryCorePaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryCoreGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryCoreFull `
    --paste-dir $repositoryCorePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository core graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryCoreFull, $repositoryCorePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCoreContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryCoreFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository core full-graph contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCoreContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryCorePaste `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository core paste-graph contracts failed with exit code $LASTEXITCODE."
}
$repositoryCorePairs = @(
    @('reset-repository-result-v1.eddgraph', 'reset-repository-result-v1.eddgraph'),
    @('find-record-index-v1.eddgraph', 'find-record-index-v1.eddgraph')
)
foreach ($pair in $repositoryCorePairs) {
    $generated = Join-Path $repositoryCoreFull $pair[0]
    $checkedIn = Join-Path $ProjectRoot "tools\blueprint\snippets\$($pair[1])"
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $generated).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository core full graph is not deterministic: $($pair[0])"
    }
    $generatedPaste = Join-Path $repositoryCorePaste $pair[0].Replace('.eddgraph', '-paste.eddgraph')
    $checkedInPaste = Join-Path $ProjectRoot "tools\blueprint\snippets\$($pair[1].Replace('.eddgraph', '-paste.eddgraph'))"
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $generatedPaste).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedInPaste).Hash) {
        throw "Repository core paste graph is not deterministic: $($pair[0])"
    }
}

# Live editor round-trips retain Unreal-assigned GUIDs and layout, so they are
# semantic installation evidence rather than deterministic generator outputs.
$repositoryCoreLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
foreach ($graph in Get-ChildItem -LiteralPath $repositoryCoreLive -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCoreContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryCoreLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository core live-round-trip contracts failed with exit code $LASTEXITCODE."
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

& python (Join-Path $ProjectRoot 'tools\history\test_draft_history.py')
if ($LASTEXITCODE -ne 0) {
    throw "Draft history state contracts failed with exit code $LASTEXITCODE."
}

$historyNonce = [guid]::NewGuid().ToString('N')
$generatedHistoryDir = Join-Path $scratchRoot "edd-history-$historyNonce"
$generatedHistoryPasteDir = Join-Path $scratchRoot "edd-history-$historyNonce-paste"
$generatedHistoryRepeatDir = Join-Path $scratchRoot "edd-history-$historyNonce-repeat"
$generatedHistoryRepeatPasteDir = Join-Path $scratchRoot "edd-history-$historyNonce-repeat-paste"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $generatedHistoryDir `
    --paste-dir $generatedHistoryPasteDir
if ($LASTEXITCODE -ne 0) {
    throw "Draft history graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $generatedHistoryRepeatDir `
    --paste-dir $generatedHistoryRepeatPasteDir
if ($LASTEXITCODE -ne 0) {
    throw "Repeated draft history graph generation failed with exit code $LASTEXITCODE."
}
foreach ($directoryPair in @(
    @($generatedHistoryDir, $generatedHistoryRepeatDir),
    @($generatedHistoryPasteDir, $generatedHistoryRepeatPasteDir)
)) {
    foreach ($file in Get-ChildItem -LiteralPath $directoryPair[0] -File) {
        $peer = Join-Path $directoryPair[1] $file.Name
        if (-not (Test-Path -LiteralPath $peer -PathType Leaf) -or
            (Get-FileHash -Algorithm SHA256 $file.FullName).Hash -ne
            (Get-FileHash -Algorithm SHA256 $peer).Hash) {
            throw "Draft history graph generation is not deterministic: $($file.Name)"
        }
        & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $file.FullName
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedHistoryDir
if ($LASTEXITCODE -ne 0) {
    throw "Generated draft history contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedHistoryPasteDir --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated draft history paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryContracts.py') `
    --project-root $ProjectRoot --input-dir (Join-Path $ProjectRoot 'tools\blueprint\snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Checked draft history contracts failed with exit code $LASTEXITCODE."
}

$historyIntegrationNonce = [guid]::NewGuid().ToString('N')
$generatedHistoryIntegrationDir = Join-Path $scratchRoot "edd-history-integration-$historyIntegrationNonce"
$generatedHistoryIntegrationRepeatDir = Join-Path $scratchRoot "edd-history-integration-$historyIntegrationNonce-repeat"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryIntegrationGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedHistoryIntegrationDir
if ($LASTEXITCODE -ne 0) {
    throw "Draft history integration graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryIntegrationGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedHistoryIntegrationRepeatDir
if ($LASTEXITCODE -ne 0) {
    throw "Repeated draft history integration graph generation failed with exit code $LASTEXITCODE."
}
$historyIntegrationFiles = @(
    'capture-current-waypoint-history-v1.eddgraph',
    'capture-current-waypoint-history-v1-paste.eddgraph',
    'replace-selected-waypoint-history-v1.eddgraph',
    'replace-selected-waypoint-history-v1-paste.eddgraph',
    'delete-selected-waypoint-history-v1.eddgraph',
    'delete-selected-waypoint-history-v1-paste.eddgraph'
)
foreach ($file in $historyIntegrationFiles) {
    $first = Join-Path $generatedHistoryIntegrationDir $file
    $second = Join-Path $generatedHistoryIntegrationRepeatDir $file
    if ((Get-FileHash -Algorithm SHA256 $first).Hash -ne (Get-FileHash -Algorithm SHA256 $second).Hash) {
        throw "Draft history integration graph generation is not deterministic: $file"
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $first
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedHistoryIntegrationDir
if ($LASTEXITCODE -ne 0) {
    throw "Generated draft history integration contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedHistoryIntegrationDir --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated draft history integration paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryIntegrationContracts.py') `
    --project-root $ProjectRoot --input-dir (Join-Path $ProjectRoot 'tools\blueprint\snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Checked draft history integration contracts failed with exit code $LASTEXITCODE."
}

$mutationDiagnosticNonce = [guid]::NewGuid().ToString('N')
$generatedMutationDiagnosticDir = Join-Path $scratchRoot "edd-mutation-diagnostic-$mutationDiagnosticNonce"
$generatedMutationDiagnosticRepeatDir = Join-Path $scratchRoot "edd-mutation-diagnostic-$mutationDiagnosticNonce-repeat"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-MutationDiagnosticGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedMutationDiagnosticDir
if ($LASTEXITCODE -ne 0) {
    throw "Mutation diagnostic graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-MutationDiagnosticGraphs.py') `
    --project-root $ProjectRoot --output-dir $generatedMutationDiagnosticRepeatDir
if ($LASTEXITCODE -ne 0) {
    throw "Repeated mutation diagnostic graph generation failed with exit code $LASTEXITCODE."
}
$mutationDiagnosticFiles = @(
    'capture-current-waypoint-diagnostics-v1.eddgraph',
    'capture-current-waypoint-diagnostics-v1-paste.eddgraph',
    'replace-selected-waypoint-diagnostics-v1.eddgraph',
    'replace-selected-waypoint-diagnostics-v1-paste.eddgraph',
    'delete-selected-waypoint-diagnostics-v1.eddgraph',
    'delete-selected-waypoint-diagnostics-v1-paste.eddgraph'
)
foreach ($file in $mutationDiagnosticFiles) {
    $first = Join-Path $generatedMutationDiagnosticDir $file
    $second = Join-Path $generatedMutationDiagnosticRepeatDir $file
    if ((Get-FileHash -Algorithm SHA256 $first).Hash -ne (Get-FileHash -Algorithm SHA256 $second).Hash) {
        throw "Mutation diagnostic graph generation is not deterministic: $file"
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $first
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-MutationDiagnosticContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedMutationDiagnosticDir
if ($LASTEXITCODE -ne 0) {
    throw "Generated mutation diagnostic contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-MutationDiagnosticContracts.py') `
    --project-root $ProjectRoot --input-dir $generatedMutationDiagnosticDir --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated mutation diagnostic paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-MutationDiagnosticContracts.py') `
    --project-root $ProjectRoot --input-dir (Join-Path $ProjectRoot 'tools\blueprint\snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Checked mutation diagnostic contracts failed with exit code $LASTEXITCODE."
}

$historyDispatchNonce = [guid]::NewGuid().ToString('N')
$historyDispatchBase = Join-Path $ProjectRoot 'tools\blueprint\snippets\client-director-event-playback-v1.eddgraph'
$generatedHistoryDispatch = Join-Path $scratchRoot "edd-history-dispatch-$historyDispatchNonce.eddgraph"
$generatedHistoryDispatchRepeat = Join-Path $scratchRoot "edd-history-dispatch-$historyDispatchNonce-repeat.eddgraph"
$generatedHistoryDispatchIdempotent = Join-Path $scratchRoot "edd-history-dispatch-$historyDispatchNonce-idempotent.eddgraph"
$checkedHistoryDispatch = Join-Path $ProjectRoot 'tools\blueprint\snippets\client-director-event-graph.eddgraph'
foreach ($output in @($generatedHistoryDispatch, $generatedHistoryDispatchRepeat)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryDispatch.py') `
        --input $historyDispatchBase --output $output
    if ($LASTEXITCODE -ne 0) {
        throw "Draft history dispatch generation failed with exit code $LASTEXITCODE."
    }
}
if ((Get-FileHash -Algorithm SHA256 $generatedHistoryDispatch).Hash -ne
    (Get-FileHash -Algorithm SHA256 $generatedHistoryDispatchRepeat).Hash) {
    throw 'Draft history dispatch generation is not deterministic.'
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-DraftHistoryDispatch.py') `
    --input $generatedHistoryDispatch --output $generatedHistoryDispatchIdempotent
if ($LASTEXITCODE -ne 0) {
    throw "Idempotent draft history dispatch generation failed with exit code $LASTEXITCODE."
}
if ((Get-FileHash -Algorithm SHA256 $generatedHistoryDispatch).Hash -ne
    (Get-FileHash -Algorithm SHA256 $generatedHistoryDispatchIdempotent).Hash) {
    throw 'Draft history dispatch generation is not idempotent.'
}
foreach ($graph in @($generatedHistoryDispatch, $checkedHistoryDispatch)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-WaypointCaptureContracts.py') `
        --capture (Join-Path $ProjectRoot 'tools\blueprint\snippets\capture-current-waypoint.eddgraph') `
        --event $graph
    if ($LASTEXITCODE -ne 0) {
        throw "Waypoint authoring contracts failed for history dispatch with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-WaypointFeedbackContracts.py') --event $graph
    if ($LASTEXITCODE -ne 0) {
        throw "Waypoint feedback contracts failed for history dispatch with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-LinearPlaybackDispatchContracts.py') --event $graph
    if ($LASTEXITCODE -ne 0) {
        throw "Linear playback contracts failed for history dispatch with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-DraftHistoryDispatchContracts.py') --event $graph
    if ($LASTEXITCODE -ne 0) {
        throw "Draft history dispatch contracts failed with exit code $LASTEXITCODE."
    }
}

$cleanFrameNonce = [guid]::NewGuid().ToString('N')
$cleanFrameDir = Join-Path $scratchRoot "edd-clean-frame-$cleanFrameNonce"
$cleanFramePasteDir = Join-Path $scratchRoot "edd-clean-frame-$cleanFrameNonce-paste"
$cleanFrameRepeatDir = Join-Path $scratchRoot "edd-clean-frame-$cleanFrameNonce-repeat"
$cleanFrameRepeatPasteDir = Join-Path $scratchRoot "edd-clean-frame-$cleanFrameNonce-repeat-paste"
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CleanFrameGraphs.py') `
    --project-root $ProjectRoot --output-dir $cleanFrameDir --paste-dir $cleanFramePasteDir
if ($LASTEXITCODE -ne 0) {
    throw "Clean Frame graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CleanFrameGraphs.py') `
    --project-root $ProjectRoot --output-dir $cleanFrameRepeatDir --paste-dir $cleanFrameRepeatPasteDir
if ($LASTEXITCODE -ne 0) {
    throw "Repeated Clean Frame graph generation failed with exit code $LASTEXITCODE."
}
foreach ($directoryPair in @(
    @($cleanFrameDir, $cleanFrameRepeatDir),
    @($cleanFramePasteDir, $cleanFrameRepeatPasteDir)
)) {
    foreach ($file in Get-ChildItem -LiteralPath $directoryPair[0] -File) {
        $peer = Join-Path $directoryPair[1] $file.Name
        if ((Get-FileHash -Algorithm SHA256 $file.FullName).Hash -ne
            (Get-FileHash -Algorithm SHA256 $peer).Hash) {
            throw "Clean Frame graph generation is not deterministic: $($file.Name)"
        }
        & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $file.FullName
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameContracts.py') `
    --project-root $ProjectRoot `
    --enter (Join-Path $cleanFrameDir 'enter-clean-frame-v1.eddgraph') `
    --exit (Join-Path $cleanFrameDir 'exit-clean-frame-v1.eddgraph') `
    --toggle (Join-Path $cleanFrameDir 'toggle-clean-frame-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Generated Clean Frame contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameContracts.py') `
    --project-root $ProjectRoot `
    --enter (Join-Path $cleanFramePasteDir 'enter-clean-frame-v1-paste.eddgraph') `
    --exit (Join-Path $cleanFramePasteDir 'exit-clean-frame-v1-paste.eddgraph') `
    --toggle (Join-Path $cleanFramePasteDir 'toggle-clean-frame-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated Clean Frame paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameContracts.py') `
    --project-root $ProjectRoot `
    --enter (Join-Path $ProjectRoot 'tools\blueprint\snippets\enter-clean-frame-v1.eddgraph') `
    --exit (Join-Path $ProjectRoot 'tools\blueprint\snippets\exit-clean-frame-v1.eddgraph') `
    --toggle (Join-Path $ProjectRoot 'tools\blueprint\snippets\toggle-clean-frame-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Checked live Clean Frame contracts failed with exit code $LASTEXITCODE."
}

$cleanFrameIntegrationDir = Join-Path $scratchRoot "edd-clean-frame-integration-$cleanFrameNonce"
$cleanFrameIntegrationRepeatDir = Join-Path $scratchRoot "edd-clean-frame-integration-$cleanFrameNonce-repeat"
New-Item -ItemType Directory -Path $cleanFrameIntegrationDir -Force | Out-Null
New-Item -ItemType Directory -Path $cleanFrameIntegrationRepeatDir -Force | Out-Null
foreach ($directory in @($cleanFrameIntegrationDir, $cleanFrameIntegrationRepeatDir)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CleanFrameIntegrationGraphs.py') `
        --project-root $ProjectRoot `
        --exit-output (Join-Path $directory 'exit-drone-mode-clean-frame.eddgraph') `
        --dispatch-output (Join-Path $directory 'client-director-event-graph-clean-frame.eddgraph')
    if ($LASTEXITCODE -ne 0) {
        throw "Clean Frame integration generation failed with exit code $LASTEXITCODE."
    }
}
foreach ($fileName in @(
    'exit-drone-mode-clean-frame.eddgraph',
    'exit-drone-mode-clean-frame-paste.eddgraph',
    'client-director-event-graph-clean-frame.eddgraph'
)) {
    $first = Join-Path $cleanFrameIntegrationDir $fileName
    $second = Join-Path $cleanFrameIntegrationRepeatDir $fileName
    if ((Get-FileHash -Algorithm SHA256 $first).Hash -ne (Get-FileHash -Algorithm SHA256 $second).Hash) {
        throw "Clean Frame integration generation is not deterministic: $fileName"
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $first
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameIntegrationContracts.py') `
    --project-root $ProjectRoot `
    --exit (Join-Path $cleanFrameIntegrationDir 'exit-drone-mode-clean-frame.eddgraph') `
    --dispatch (Join-Path $cleanFrameIntegrationDir 'client-director-event-graph-clean-frame.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Generated Clean Frame integration contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameIntegrationContracts.py') `
    --project-root $ProjectRoot `
    --exit (Join-Path $cleanFrameIntegrationDir 'exit-drone-mode-clean-frame-paste.eddgraph') `
    --dispatch (Join-Path $cleanFrameIntegrationDir 'client-director-event-graph-clean-frame.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Generated Clean Frame integration paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CleanFrameIntegrationContracts.py') `
    --project-root $ProjectRoot `
    --exit (Join-Path $ProjectRoot 'tools\blueprint\snippets\exit-drone-mode-clean-frame.eddgraph') `
    --dispatch (Join-Path $ProjectRoot 'tools\blueprint\snippets\client-director-event-graph-clean-frame.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Checked live Clean Frame integration contracts failed with exit code $LASTEXITCODE."
}
