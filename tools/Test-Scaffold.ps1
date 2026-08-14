[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$RequireMvpAssets
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

& python (Join-Path $ProjectRoot 'tools\unreal\test_invoke_unreal_remote.py')
if ($LASTEXITCODE -ne 0) {
    throw "Unreal remote-execution helper contracts failed with exit code $LASTEXITCODE."
}

& (Join-Path $ProjectRoot 'tools\Test-SyncDevKitContent.ps1') -ProjectRoot $ProjectRoot

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
    'tools\Test-SyncDevKitContent.ps1',
    'tools\unreal\Quit-EnhancedEditorSafely.py',
    'tools\Test-RepositoryBudget.ps1',
    'tools\Invoke-UnrealPython.ps1',
    'tools\Start-EnhancedDevKitRemote.ps1',
    'tools\Test-RepositorySaveGame.ps1',
    'tools\Test-RepositoryService.ps1',
    'tools\unreal\invoke_unreal_remote.py',
    'tools\unreal\test_invoke_unreal_remote.py',
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
    'tools\unreal\Compile-And-SaveRepository.py',
    'tools\unreal\Validate-RepositoryPersistenceWriter.py',
    'tools\unreal\Validate-RepositoryPrivateDraftLoad.py',
    'tools\unreal\Validate-RepositoryPrivateCreate.py',
    'tools\unreal\Validate-RepositoryPrivateCreateRestart.py',
    'tools\unreal\Validate-RepositoryPrivateSave.py',
    'tools\unreal\Validate-RepositoryPrivateSaveRestart.py',
    'tools\unreal\Validate-RepositoryPrivateList.py',
    'tools\unreal\Validate-RepositoryPrivateListRestart.py',
    'tools\unreal\Validate-RepositoryPrivateDelete.py',
    'tools\unreal\Validate-RepositoryPrivateDeleteRestart.py',
    'tools\unreal\Validate-RepositoryPublishDraft.py',
    'tools\unreal\Validate-RepositoryPublishDraftRestart.py',
    'tools\unreal\Validate-RepositoryUnpublish.py',
    'tools\unreal\Validate-RepositoryUnpublishRestart.py',
    'tools\unreal\Validate-RepositoryPublicList.py',
    'tools\unreal\Validate-RepositoryPublicListRestart.py',
    'tools\unreal\Validate-RepositoryPublishedFetch.py',
    'tools\unreal\Validate-RepositoryPublishedFetchRestart.py',
    'tools\unreal\Validate-RepositoryPublishedClone.py',
    'tools\unreal\Validate-RepositoryPublishedCloneRestart.py',
    'tools\unreal\Enable-EnhancedEditorRemoteExecution.ps1',
    'tools\unreal\Test-EnhancedEditorRemoteExecutionConfig.ps1',
    'tools\unreal\Get-EnhancedEditorWindows.ps1',
    'tools\unreal\Save-WindowScreenshot.ps1',
    'tools\unreal\Inspect-PythonRemoteExecutionSettings.py',
    'tools\unreal\Read-RepositoryPersistenceWriter.py',
    'tools\unreal\Open-RepositoryServiceEditor.py',
    'tools\unreal\Validate-RepositoryJsonCodec.py',
    'tools\unreal\Probe-HashEncodingApi.py',
    'tools\unreal\Prepare-RepositoryJsonNodeProbe.py',
    'tools\unreal\Inspect-RepositoryJsonBlueprintApi.py',
    'tools\unreal\Inspect-QuaternionBlueprintApi.py',
    'tools\unreal\Delete-RepositoryJsonNodeProbe.py',
    'tools\unreal\Prepare-RepositorySaveGameNodeProbe.py',
    'tools\unreal\Delete-RepositorySaveGameNodeProbe.py',
    'tools\playback\linear_reference.py',
    'tools\playback\test_linear_reference.py',
    'tools\trajectory\cinematic_reference.py',
    'tools\trajectory\test_cinematic_reference.py',
    'tools\trajectory\orientation_reference.py',
    'tools\trajectory\test_orientation_reference.py',
    'tools\trajectory\orientation_blueprint_schema.json',
    'tools\trajectory\test_orientation_blueprint_schema.py',
    'tools\trajectory\arc_table_blueprint_schema.json',
    'tools\trajectory\test_arc_table_blueprint_schema.py',
    'tools\trajectory\adaptive_arc_blueprint_schema.json',
    'tools\trajectory\test_adaptive_arc_blueprint_schema.py',
    'tools\trajectory\position_route_blueprint_schema.json',
    'tools\trajectory\test_position_route_blueprint_schema.py',
    'tools\trajectory\cinematic_pose_reference.py',
    'tools\trajectory\test_cinematic_pose_reference.py',
    'tools\trajectory\cinematic_pose_blueprint_schema.json',
    'tools\trajectory\test_cinematic_pose_blueprint_schema.py',
    'tools\trajectory\flight_profile_reference.py',
    'tools\trajectory\test_flight_profile_reference.py',
    'tools\trajectory\flight_profile_blueprint_schema.json',
    'tools\trajectory\test_flight_profile_blueprint_schema.py',
    'tools\trajectory\smoothed_flight_profile_reference.py',
    'tools\trajectory\test_smoothed_flight_profile_reference.py',
    'tools\trajectory\smoothed_flight_profile_blueprint_schema.json',
    'tools\trajectory\test_smoothed_flight_profile_blueprint_schema.py',
    'tools\trajectory\airframe_gimbal_reference.py',
    'tools\trajectory\test_airframe_gimbal_reference.py',
    'tools\trajectory\airframe_gimbal_blueprint_schema.json',
    'tools\trajectory\test_airframe_gimbal_blueprint_schema.py',
    'tools\trajectory\airframe_gimbal_prebake_reference.py',
    'tools\trajectory\test_airframe_gimbal_prebake_reference.py',
    'tools\trajectory\airframe_gimbal_prebake_blueprint_schema.json',
    'tools\trajectory\test_airframe_gimbal_prebake_blueprint_schema.py',
    'tools\trajectory\airframe_desired_stream_reference.py',
    'tools\trajectory\test_airframe_desired_stream_reference.py',
    'tools\trajectory\airframe_desired_stream_blueprint_schema.json',
    'tools\trajectory\test_airframe_desired_stream_blueprint_schema.py',
    'tools\trajectory\airframe_source_sampling_reference.py',
    'tools\trajectory\test_airframe_source_sampling_reference.py',
    'tools\trajectory\airframe_source_sampling_blueprint_schema.json',
    'tools\trajectory\test_airframe_source_sampling_blueprint_schema.py',
    'tools\trajectory\compiled_document_source_adapter_reference.py',
    'tools\trajectory\test_compiled_document_source_adapter_reference.py',
    'tools\trajectory\compiled_document_source_adapter_blueprint_schema.json',
    'tools\trajectory\test_compiled_document_source_adapter_blueprint_schema.py',
    'tools\trajectory\camera_scalar_track_reference.py',
    'tools\trajectory\test_camera_scalar_track_reference.py',
    'tools\trajectory\camera_scalar_track_blueprint_schema.json',
    'tools\trajectory\test_camera_scalar_track_blueprint_schema.py',
    'tools\trajectory\camera_channel_assembly_reference.py',
    'tools\trajectory\test_camera_channel_assembly_reference.py',
    'tools\trajectory\camera_channel_assembly_blueprint_schema.json',
    'tools\trajectory\test_camera_channel_assembly_blueprint_schema.py',
    'tools\trajectory\camera_engine_application_reference.py',
    'tools\trajectory\test_camera_engine_application_reference.py',
    'tools\trajectory\camera_engine_application_blueprint_schema.json',
    'tools\trajectory\test_camera_engine_application_blueprint_schema.py',
    'tools\trajectory\camera_engine_property_candidates_v1.json',
    'tools\trajectory\camera_engine_property_manifest_enhanced_5_6_1.json',
    'tools\trajectory\camera_engine_property_probe_reference.py',
    'tools\trajectory\test_camera_engine_property_probe_reference.py',
    'tools\trajectory\camera_focus_helper_reference.py',
    'tools\trajectory\test_camera_focus_helper_reference.py',
    'tools\trajectory\camera_focus_helper_blueprint_schema.json',
    'tools\trajectory\test_camera_focus_helper_blueprint_schema.py',
    'tools\trajectory\camera_dof_diagnostics_reference.py',
    'tools\trajectory\test_camera_dof_diagnostics_reference.py',
    'tools\trajectory\camera_dof_diagnostics_blueprint_schema.json',
    'tools\trajectory\test_camera_dof_diagnostics_blueprint_schema.py',
    'tools\trajectory\camera_dolly_zoom_reference.py',
    'tools\trajectory\test_camera_dolly_zoom_reference.py',
    'tools\trajectory\camera_dolly_zoom_blueprint_schema.json',
    'tools\trajectory\test_camera_dolly_zoom_blueprint_schema.py',
    'tools\trajectory\camera_base_look_reference.py',
    'tools\trajectory\test_camera_base_look_reference.py',
    'tools\trajectory\camera_base_look_blueprint_schema.json',
    'tools\trajectory\test_camera_base_look_blueprint_schema.py',
    'tools\trajectory\camera_viewer_comfort_reference.py',
    'tools\trajectory\test_camera_viewer_comfort_reference.py',
    'tools\trajectory\camera_viewer_comfort_blueprint_schema.json',
    'tools\trajectory\test_camera_viewer_comfort_blueprint_schema.py',
    'tools\trajectory\camera_operator_override_reference.py',
    'tools\trajectory\test_camera_operator_override_reference.py',
    'tools\trajectory\camera_operator_override_blueprint_schema.json',
    'tools\trajectory\test_camera_operator_override_blueprint_schema.py',
    'tools\blueprint\Build-CameraOperatorOverrideResetGraph.py',
    'tools\blueprint\Test-CameraOperatorOverrideResetContracts.py',
    'tools\blueprint\snippets\reset-camera-operator-override-step-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-operator-override-step-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraOperatorOverrideValidationGraph.py',
    'tools\blueprint\Test-CameraOperatorOverrideValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-operator-override-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-operator-override-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraOperatorOverrideTranslationGraph.py',
    'tools\blueprint\Test-CameraOperatorOverrideTranslationContracts.py',
    'tools\blueprint\snippets\build-camera-operator-translation-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-operator-translation-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortResetGraph.py',
    'tools\blueprint\Test-CameraViewerComfortResetContracts.py',
    'tools\blueprint\snippets\reset-camera-viewer-comfort-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-viewer-comfort-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-camera-viewer-comfort-v1.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortValidationGraph.py',
    'tools\blueprint\Test-CameraViewerComfortValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-viewer-comfort-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-viewer-comfort-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-viewer-comfort-inputs-v1.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortMotionGraph.py',
    'tools\blueprint\Test-CameraViewerComfortMotionContracts.py',
    'tools\blueprint\snippets\build-camera-viewer-comfort-motion-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-viewer-comfort-motion-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-camera-viewer-comfort-motion-v1.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortChannelsGraph.py',
    'tools\blueprint\Test-CameraViewerComfortChannelsContracts.py',
    'tools\blueprint\snippets\build-camera-viewer-comfort-channels-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-viewer-comfort-channels-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-camera-viewer-comfort-channels-v1.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortCommitGraph.py',
    'tools\blueprint\Test-CameraViewerComfortCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-viewer-comfort-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-viewer-comfort-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-camera-viewer-comfort-v1.eddgraph',
    'tools\blueprint\Build-CameraViewerComfortApplyGraph.py',
    'tools\blueprint\Test-CameraViewerComfortApplyContracts.py',
    'tools\blueprint\snippets\apply-camera-viewer-comfort-v1.eddgraph',
    'tools\blueprint\snippets\apply-camera-viewer-comfort-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\apply-camera-viewer-comfort-v1.eddgraph',
    'tools\unreal\Configure-CameraViewerComfort.py',
    'tools\unreal\Restore-CameraViewerComfortSchemaDefaults.py',
    'tools\unreal\Validate-CameraViewerComfortRuntime.py',
    'tools\unreal\Validate-CameraViewerComfortPIE.py',
    'tools\unreal\test_camera_viewer_comfort_validators.py',
    'tools\blueprint\Build-CameraBaseLookResetGraph.py',
    'tools\blueprint\Test-CameraBaseLookResetContracts.py',
    'tools\blueprint\snippets\reset-camera-look-composition-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-look-composition-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-camera-look-composition-v1.eddgraph',
    'tools\blueprint\Build-CameraBaseLookValidationGraph.py',
    'tools\blueprint\Test-CameraBaseLookValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-look-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-look-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-look-inputs-v1.eddgraph',
    'tools\blueprint\Build-CameraBaseLookBaseValuesGraph.py',
    'tools\blueprint\Test-CameraBaseLookBaseValuesContracts.py',
    'tools\blueprint\snippets\build-camera-look-base-values-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-look-base-values-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-camera-look-base-values-v1.eddgraph',
    'tools\blueprint\Build-CameraBaseLookOverridesGraph.py',
    'tools\blueprint\Test-CameraBaseLookOverridesContracts.py',
    'tools\blueprint\snippets\apply-camera-look-authored-overrides-v1.eddgraph',
    'tools\blueprint\snippets\apply-camera-look-authored-overrides-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\apply-camera-look-authored-overrides-v1.eddgraph',
    'tools\blueprint\Build-CameraBaseLookCommitGraph.py',
    'tools\blueprint\Test-CameraBaseLookCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-look-composition-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-look-composition-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-camera-look-composition-v1.eddgraph',
    'tools\blueprint\Build-CameraBaseLookComposeGraph.py',
    'tools\blueprint\Test-CameraBaseLookComposeContracts.py',
    'tools\blueprint\snippets\compose-camera-look-v1.eddgraph',
    'tools\blueprint\snippets\compose-camera-look-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compose-camera-look-v1.eddgraph',
    'tools\unreal\Configure-CameraBaseLook.py',
    'tools\unreal\Restore-CameraBaseLookSchemaDefaults.py',
    'tools\unreal\Validate-CameraBaseLookRuntime.py',
    'tools\unreal\Validate-CameraBaseLookPIE.py',
    'tools\unreal\test_camera_base_look_validators.py',
    'tools\blueprint\Build-CameraDollyZoomResetGraph.py',
    'tools\blueprint\Test-CameraDollyZoomResetContracts.py',
    'tools\blueprint\snippets\reset-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-dolly-zoom-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDollyZoomValidationGraph.py',
    'tools\blueprint\Test-CameraDollyZoomValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-dolly-zoom-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-dolly-zoom-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDollyZoomCandidatesGraph.py',
    'tools\blueprint\Test-CameraDollyZoomCandidatesContracts.py',
    'tools\blueprint\snippets\build-camera-dolly-zoom-candidates-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-dolly-zoom-candidates-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDollyZoomCommitGraph.py',
    'tools\blueprint\Test-CameraDollyZoomCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-dolly-zoom-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDollyZoomCompileGraph.py',
    'tools\blueprint\Test-CameraDollyZoomCompileContracts.py',
    'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py',
    'tools\blueprint\Test-BlueprintGraphTopologyMatch.py',
    'tools\blueprint\snippets\compile-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\snippets\compile-camera-dolly-zoom-v1-paste.eddgraph',
    'tools\unreal\Configure-CameraDollyZoom.py',
    'tools\unreal\Restore-CameraDollyZoomSchemaDefaults.py',
    'tools\unreal\Validate-CameraDollyZoomRuntime.py',
    'tools\unreal\Validate-CameraDollyZoomPIE.py',
    'tools\unreal\test_camera_dolly_zoom_validators.py',
    'tools\blueprint\live-snippets\reset-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-dolly-zoom-inputs-v1.eddgraph',
    'tools\blueprint\live-snippets\build-camera-dolly-zoom-candidates-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-camera-dolly-zoom-v1.eddgraph',
    'tools\blueprint\Build-CameraDofDiagnosticsResetGraph.py',
    'tools\blueprint\Test-CameraDofDiagnosticsResetContracts.py',
    'tools\blueprint\snippets\reset-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-dof-diagnostics-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDofDiagnosticsStageGraph.py',
    'tools\blueprint\Test-CameraDofDiagnosticsStageContracts.py',
    'tools\blueprint\snippets\stage-evaluated-camera-dof-frame-v1.eddgraph',
    'tools\blueprint\snippets\stage-evaluated-camera-dof-frame-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDofDiagnosticsComputeGraph.py',
    'tools\blueprint\Test-CameraDofDiagnosticsComputeContracts.py',
    'tools\blueprint\snippets\compute-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\compute-camera-dof-diagnostics-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraDofDiagnosticsEvaluateGraph.py',
    'tools\blueprint\Test-CameraDofDiagnosticsEvaluateContracts.py',
    'tools\blueprint\snippets\evaluate-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-camera-dof-diagnostics-v1-paste.eddgraph',
    'tools\unreal\Configure-CameraDofDiagnostics.py',
    'tools\unreal\Restore-CameraDofDiagnosticsSchemaDefaults.py',
    'tools\unreal\Validate-CameraDofDiagnosticsRuntime.py',
    'tools\unreal\Validate-CameraDofDiagnosticsPIE.py',
    'tools\unreal\test_camera_dof_diagnostics_validators.py',
    'tools\blueprint\live-snippets\reset-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-evaluated-camera-dof-frame-v1.eddgraph',
    'tools\blueprint\live-snippets\compute-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\live-snippets\evaluate-camera-dof-diagnostics-v1.eddgraph',
    'tools\blueprint\Build-CameraFocusCompileResetGraph.py',
    'tools\blueprint\Test-CameraFocusCompileResetContracts.py',
    'tools\blueprint\snippets\reset-camera-focus-compile-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-focus-compile-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraFocusSetHereGraph.py',
    'tools\blueprint\Test-CameraFocusSetHereContracts.py',
    'tools\blueprint\snippets\set-camera-focus-here-v1.eddgraph',
    'tools\blueprint\snippets\set-camera-focus-here-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraFocusValidationGraph.py',
    'tools\blueprint\Test-CameraFocusValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-focus-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-focus-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraFocusCandidatesGraph.py',
    'tools\blueprint\Test-CameraFocusCandidatesContracts.py',
    'tools\blueprint\snippets\build-camera-focus-distance-candidates-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-focus-distance-candidates-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraFocusCommitGraph.py',
    'tools\blueprint\Test-CameraFocusCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-focus-distance-channel-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-focus-distance-channel-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraFocusCompileGraph.py',
    'tools\blueprint\Test-CameraFocusCompileContracts.py',
    'tools\blueprint\snippets\compile-camera-focus-distance-channel-v1.eddgraph',
    'tools\blueprint\snippets\compile-camera-focus-distance-channel-v1-paste.eddgraph',
    'tools\unreal\Configure-CameraFocusHelper.py',
    'tools\unreal\Restore-CameraFocusHelperSchemaDefaults.py',
    'tools\unreal\Validate-CameraFocusHelperRuntime.py',
    'tools\unreal\Validate-CameraFocusHelperPIE.py',
    'tools\unreal\test_camera_focus_helper_validators.py',
    'tools\blueprint\live-snippets\reset-camera-focus-compile-v1.eddgraph',
    'tools\blueprint\live-snippets\set-camera-focus-here-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-focus-inputs-v1.eddgraph',
    'tools\blueprint\live-snippets\build-camera-focus-distance-candidates-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-camera-focus-distance-channel-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-camera-focus-distance-channel-v1.eddgraph',
    'tools\unreal\Probe-CameraEngineProperties.py',
    'tools\blueprint\Test-CameraEngineNativeNodeForms.py',
    'tools\blueprint\templates\camera-engine-basic-node-forms.eddgraph',
    'tools\blueprint\templates\camera-engine-struct-node-forms.eddgraph',
    'tools\blueprint\Build-CameraEngineApplicationResetGraph.py',
    'tools\blueprint\Test-CameraEngineApplicationResetContracts.py',
    'tools\blueprint\snippets\reset-camera-engine-application-result-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-engine-application-result-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineApplicationStageGraph.py',
    'tools\blueprint\Test-CameraEngineApplicationStageContracts.py',
    'tools\blueprint\snippets\stage-evaluated-camera-channel-frame-v1.eddgraph',
    'tools\blueprint\snippets\stage-evaluated-camera-channel-frame-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineApplicationValidationGraph.py',
    'tools\blueprint\Test-CameraEngineApplicationValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-engine-application-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-engine-application-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineStateCaptureGraph.py',
    'tools\blueprint\Test-CameraEngineStateCaptureContracts.py',
    'tools\blueprint\snippets\capture-camera-engine-state-v1.eddgraph',
    'tools\blueprint\snippets\capture-camera-engine-state-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineFrameApplyGraph.py',
    'tools\blueprint\Test-CameraEngineFrameApplyContracts.py',
    'tools\blueprint\snippets\apply-camera-engine-frame-v1.eddgraph',
    'tools\blueprint\snippets\apply-camera-engine-frame-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineStateRestoreGraph.py',
    'tools\blueprint\Test-CameraEngineStateRestoreContracts.py',
    'tools\blueprint\snippets\restore-camera-engine-state-v1.eddgraph',
    'tools\blueprint\snippets\restore-camera-engine-state-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraEngineApplicationGraph.py',
    'tools\blueprint\Test-CameraEngineApplicationContracts.py',
    'tools\blueprint\snippets\apply-evaluated-camera-channel-frame-v1.eddgraph',
    'tools\blueprint\snippets\apply-evaluated-camera-channel-frame-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-camera-engine-application-result-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-evaluated-camera-channel-frame-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-engine-application-inputs-v1.eddgraph',
    'tools\blueprint\live-snippets\capture-camera-engine-state-v1.eddgraph',
    'tools\blueprint\live-snippets\apply-camera-engine-frame-v1.eddgraph',
    'tools\blueprint\live-snippets\restore-camera-engine-state-v1.eddgraph',
    'tools\blueprint\live-snippets\apply-evaluated-camera-channel-frame-v1.eddgraph',
    'tools\unreal\Configure-CameraEngineApplication.py',
    'tools\unreal\test_configure_camera_engine_application.py',
    'tools\unreal\Validate-CameraEngineApplicationRuntime.py',
    'tools\unreal\Validate-CameraEngineApplicationPIE.py',
    'tools\unreal\test_camera_engine_application_validators.py',
    'tools\blueprint\Build-CameraChannelCompileResetGraph.py',
    'tools\blueprint\Test-CameraChannelCompileResetContracts.py',
    'tools\blueprint\snippets\reset-camera-channel-compile-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-channel-compile-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelValidationGraph.py',
    'tools\blueprint\Test-CameraChannelValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-channel-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-channel-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelCandidateGraph.py',
    'tools\blueprint\Test-CameraChannelCandidateContracts.py',
    'tools\blueprint\snippets\compile-camera-channel-candidate-v1.eddgraph',
    'tools\blueprint\snippets\compile-camera-channel-candidate-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelCommitGraph.py',
    'tools\blueprint\Test-CameraChannelCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-channel-assembly-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-channel-assembly-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelCompileGraph.py',
    'tools\blueprint\Test-CameraChannelCompileContracts.py',
    'tools\blueprint\snippets\compile-camera-channel-assembly-v1.eddgraph',
    'tools\blueprint\snippets\compile-camera-channel-assembly-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelResultResetGraph.py',
    'tools\blueprint\Test-CameraChannelResultResetContracts.py',
    'tools\blueprint\snippets\reset-camera-channel-result-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-channel-result-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelStageGraph.py',
    'tools\blueprint\Test-CameraChannelStageContracts.py',
    'tools\blueprint\snippets\stage-compiled-camera-channel-v1.eddgraph',
    'tools\blueprint\snippets\stage-compiled-camera-channel-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelPublishGraph.py',
    'tools\blueprint\Test-CameraChannelPublishContracts.py',
    'tools\blueprint\snippets\publish-camera-channel-sample-v1.eddgraph',
    'tools\blueprint\snippets\publish-camera-channel-sample-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraChannelEvaluateGraph.py',
    'tools\blueprint\Test-CameraChannelEvaluateContracts.py',
    'tools\blueprint\snippets\evaluate-camera-channel-assembly-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-camera-channel-assembly-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-camera-channel-compile-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-camera-channel-inputs-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-camera-channel-candidate-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-camera-channel-assembly-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-camera-channel-assembly-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-camera-channel-result-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-compiled-camera-channel-v1.eddgraph',
    'tools\blueprint\live-snippets\publish-camera-channel-sample-v1.eddgraph',
    'tools\blueprint\live-snippets\evaluate-camera-channel-assembly-v1.eddgraph',
    'tools\unreal\Configure-CameraChannelAssembly.py',
    'tools\unreal\Validate-CameraChannelRuntime.py',
    'tools\unreal\Validate-CameraChannelPIE.py',
    'tools\blueprint\Build-CameraScalarTrackResetGraph.py',
    'tools\blueprint\Test-CameraScalarTrackResetContracts.py',
    'tools\blueprint\snippets\reset-camera-scalar-track-compile-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-scalar-track-compile-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackValidationGraph.py',
    'tools\blueprint\Test-CameraScalarTrackValidationContracts.py',
    'tools\blueprint\snippets\validate-camera-scalar-track-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-camera-scalar-track-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackCandidatesGraph.py',
    'tools\blueprint\Test-CameraScalarTrackCandidatesContracts.py',
    'tools\blueprint\snippets\build-camera-scalar-track-candidates-v1.eddgraph',
    'tools\blueprint\snippets\build-camera-scalar-track-candidates-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackCommitGraph.py',
    'tools\blueprint\Test-CameraScalarTrackCommitContracts.py',
    'tools\blueprint\snippets\commit-camera-scalar-track-v1.eddgraph',
    'tools\blueprint\snippets\commit-camera-scalar-track-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackCompileGraph.py',
    'tools\blueprint\Test-CameraScalarTrackCompileContracts.py',
    'tools\blueprint\snippets\compile-camera-scalar-track-v1.eddgraph',
    'tools\blueprint\snippets\compile-camera-scalar-track-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackResultResetGraph.py',
    'tools\blueprint\Test-CameraScalarTrackResultResetContracts.py',
    'tools\blueprint\snippets\reset-camera-scalar-track-result-v1.eddgraph',
    'tools\blueprint\snippets\reset-camera-scalar-track-result-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackPublishGraph.py',
    'tools\blueprint\Test-CameraScalarTrackPublishContracts.py',
    'tools\blueprint\snippets\publish-camera-scalar-track-sample-v1.eddgraph',
    'tools\blueprint\snippets\publish-camera-scalar-track-sample-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackSegmentGraph.py',
    'tools\blueprint\Test-CameraScalarTrackSegmentContracts.py',
    'tools\blueprint\snippets\evaluate-camera-scalar-track-segment-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-camera-scalar-track-segment-v1-paste.eddgraph',
    'tools\blueprint\Build-CameraScalarTrackEvaluateGraph.py',
    'tools\blueprint\Test-CameraScalarTrackEvaluateContracts.py',
    'tools\blueprint\snippets\evaluate-camera-scalar-track-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-camera-scalar-track-v1-paste.eddgraph',
    'tools\unreal\Configure-CameraScalarTrackAssembly.py',
    'tools\unreal\Restore-CameraScalarTrackSchemaDefaults.py',
    'tools\unreal\Validate-CameraScalarTrackSchemaDefaults.py',
    'tools\unreal\Validate-CameraScalarTrackRuntime.py',
    'tools\unreal\Validate-CameraScalarTrackPIE.py',
    'tools\unreal\test_camera_scalar_track_validators.py',
    'tools\blueprint\Build-AirframeDocumentAdapterResetGraph.py',
    'tools\blueprint\Test-AirframeDocumentAdapterResetContracts.py',
    'tools\blueprint\snippets\reset-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\snippets\reset-airframe-document-source-adapter-v2-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\Build-AirframeDocumentAdapterValidationGraph.py',
    'tools\blueprint\Test-AirframeDocumentAdapterValidationContracts.py',
    'tools\blueprint\snippets\validate-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\snippets\validate-airframe-document-source-adapter-v2-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\Build-AirframeDocumentAdapterCommitGraph.py',
    'tools\blueprint\Test-AirframeDocumentAdapterCommitContracts.py',
    'tools\blueprint\snippets\commit-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\snippets\commit-airframe-document-source-adapter-v2-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\Build-AirframeDocumentDiagnosticsGraph.py',
    'tools\blueprint\Test-AirframeDocumentDiagnosticsContracts.py',
    'tools\blueprint\snippets\build-airframe-document-discontinuity-diagnostics-v2.eddgraph',
    'tools\blueprint\snippets\build-airframe-document-discontinuity-diagnostics-v2-paste.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-document-discontinuity-diagnostics-v2.eddgraph',
    'tools\blueprint\Build-AirframeDocumentAdapterCompileGraph.py',
    'tools\blueprint\Test-AirframeDocumentAdapterCompileContracts.py',
    'tools\blueprint\snippets\compile-airframe-document-source-adapter-v2.eddgraph',
    'tools\blueprint\snippets\compile-airframe-document-source-adapter-v2-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-airframe-document-source-adapter-v2.eddgraph',
    'tools\unreal\Configure-AirframeDocumentAdapterAssembly.py',
    'tools\unreal\Validate-AirframeDocumentAdapterRuntime.py',
    'tools\unreal\Validate-AirframeDocumentAdapterPIE.py',
    'tools\blueprint\Build-AirframeSourceSamplingResetGraph.py',
    'tools\blueprint\Test-AirframeSourceSamplingResetContracts.py',
    'tools\blueprint\snippets\reset-airframe-source-sampling-v1.eddgraph',
    'tools\blueprint\snippets\reset-airframe-source-sampling-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-airframe-source-sampling-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourceSamplingValidationGraph.py',
    'tools\blueprint\Test-AirframeSourceSamplingValidationContracts.py',
    'tools\blueprint\snippets\validate-airframe-source-sampling-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-airframe-source-sampling-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-airframe-source-sampling-inputs-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourcePositionProfilesGraph.py',
    'tools\blueprint\Test-AirframeSourcePositionProfilesContracts.py',
    'tools\blueprint\snippets\compile-airframe-source-position-profiles-v1.eddgraph',
    'tools\blueprint\snippets\compile-airframe-source-position-profiles-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-airframe-source-position-profiles-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourcePositionBodyProfileSamplesGraph.py',
    'tools\blueprint\Test-AirframeSourcePositionBodyProfileSamplesContracts.py',
    'tools\blueprint\snippets\build-airframe-source-position-body-profile-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-source-position-body-profile-samples-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-source-position-body-profile-samples-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourceGimbalSamplesGraph.py',
    'tools\blueprint\Test-AirframeSourceGimbalSamplesContracts.py',
    'tools\blueprint\snippets\build-airframe-source-gimbal-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-source-gimbal-samples-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-source-gimbal-samples-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourceCommitGraph.py',
    'tools\blueprint\Test-AirframeSourceCommitContracts.py',
    'tools\blueprint\snippets\commit-airframe-source-samples-to-desired-v1.eddgraph',
    'tools\blueprint\snippets\commit-airframe-source-samples-to-desired-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-airframe-source-samples-to-desired-v1.eddgraph',
    'tools\blueprint\Build-AirframeSourceCompileGraph.py',
    'tools\blueprint\Test-AirframeSourceCompileContracts.py',
    'tools\blueprint\snippets\compile-airframe-source-sampling-v1.eddgraph',
    'tools\blueprint\snippets\compile-airframe-source-sampling-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-airframe-source-sampling-v1.eddgraph',
    'tools\unreal\Configure-AirframeSourceSamplingAssembly.py',
    'tools\unreal\Validate-AirframeSourceSamplingRuntime.py',
    'tools\blueprint\Build-AirframeDesiredStreamResetGraph.py',
    'tools\blueprint\Test-AirframeDesiredStreamResetContracts.py',
    'tools\blueprint\snippets\reset-airframe-desired-stream-v1.eddgraph',
    'tools\blueprint\snippets\reset-airframe-desired-stream-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredStreamValidationGraph.py',
    'tools\blueprint\Test-AirframeDesiredStreamValidationContracts.py',
    'tools\blueprint\snippets\validate-airframe-desired-stream-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-airframe-desired-stream-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredDerivativeGraph.py',
    'tools\blueprint\Test-AirframeDesiredDerivativeContracts.py',
    'tools\blueprint\snippets\build-airframe-desired-velocity-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-desired-velocity-samples-v1-paste.eddgraph',
    'tools\blueprint\snippets\build-airframe-desired-acceleration-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-desired-acceleration-samples-v1-paste.eddgraph',
    'tools\blueprint\snippets\build-airframe-desired-jerk-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-desired-jerk-samples-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredVelocitySamplerGraph.py',
    'tools\blueprint\Test-AirframeDesiredVelocitySamplerContracts.py',
    'tools\blueprint\snippets\sample-airframe-desired-velocity-at-time-v1.eddgraph',
    'tools\blueprint\snippets\sample-airframe-desired-velocity-at-time-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredPoseSamplesGraph.py',
    'tools\blueprint\Test-AirframeDesiredPoseSamplesContracts.py',
    'tools\blueprint\snippets\solve-airframe-desired-pose-samples-v1.eddgraph',
    'tools\blueprint\snippets\solve-airframe-desired-pose-samples-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredStreamCommitGraph.py',
    'tools\blueprint\Test-AirframeDesiredStreamCommitContracts.py',
    'tools\blueprint\snippets\commit-airframe-desired-stream-to-prebake-v1.eddgraph',
    'tools\blueprint\snippets\commit-airframe-desired-stream-to-prebake-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeDesiredStreamCompileGraph.py',
    'tools\blueprint\Test-AirframeDesiredStreamCompileContracts.py',
    'tools\blueprint\snippets\compile-airframe-desired-stream-v1.eddgraph',
    'tools\blueprint\snippets\compile-airframe-desired-stream-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-airframe-desired-stream-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-airframe-desired-stream-inputs-v1.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-desired-velocity-samples-v1.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-desired-acceleration-samples-v1.eddgraph',
    'tools\blueprint\live-snippets\build-airframe-desired-jerk-samples-v1.eddgraph',
    'tools\blueprint\live-snippets\sample-airframe-desired-velocity-at-time-v1.eddgraph',
    'tools\blueprint\live-snippets\solve-airframe-desired-pose-samples-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-airframe-desired-stream-to-prebake-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-airframe-desired-stream-v1.eddgraph',
    'tools\blueprint\Build-AirframePrebakeResetGraph.py',
    'tools\blueprint\Test-AirframePrebakeResetContracts.py',
    'tools\blueprint\snippets\reset-airframe-prebake-candidate-v1.eddgraph',
    'tools\blueprint\snippets\reset-airframe-prebake-candidate-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeValidationGraph.py',
    'tools\blueprint\Test-AirframePrebakeValidationContracts.py',
    'tools\blueprint\snippets\validate-airframe-prebake-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-airframe-prebake-inputs-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeNativeNodeForms.py',
    'tools\blueprint\Test-AirframePrebakeNativeNodeForms.py',
    'tools\blueprint\templates\airframe-prebake-native-node-forms.eddgraph',
    'tools\blueprint\Build-AirframeAngularRateLimitGraph.py',
    'tools\blueprint\Test-AirframeAngularRateLimitContracts.py',
    'tools\blueprint\snippets\apply-airframe-angular-rate-limit-v1.eddgraph',
    'tools\blueprint\snippets\apply-airframe-angular-rate-limit-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeSamplesGraph.py',
    'tools\blueprint\Test-AirframePrebakeSamplesContracts.py',
    'tools\blueprint\snippets\build-airframe-prebake-samples-v1.eddgraph',
    'tools\blueprint\snippets\build-airframe-prebake-samples-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeCommitGraph.py',
    'tools\blueprint\Test-AirframePrebakeCommitContracts.py',
    'tools\blueprint\snippets\commit-compiled-airframe-prebake-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-airframe-prebake-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeCompileGraph.py',
    'tools\blueprint\Test-AirframePrebakeCompileContracts.py',
    'tools\blueprint\snippets\compile-airframe-prebake-v1.eddgraph',
    'tools\blueprint\snippets\compile-airframe-prebake-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframePrebakeEvaluatorGraph.py',
    'tools\blueprint\Test-AirframePrebakeEvaluatorContracts.py',
    'tools\blueprint\snippets\evaluate-compiled-airframe-prebake-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-compiled-airframe-prebake-v1-paste.eddgraph',
    'tools\blueprint\Build-AirframeGimbalResetGraph.py',
    'tools\blueprint\Test-AirframeGimbalResetContracts.py',
    'tools\blueprint\snippets\reset-airframe-gimbal-v1.eddgraph',
    'tools\blueprint\snippets\reset-airframe-gimbal-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-airframe-gimbal-v1.eddgraph',
    'tools\blueprint\Build-AirframeGimbalValidationGraph.py',
    'tools\blueprint\Test-AirframeGimbalValidationContracts.py',
    'tools\blueprint\snippets\validate-airframe-gimbal-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-airframe-gimbal-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-airframe-gimbal-inputs-v1.eddgraph',
    'tools\blueprint\Build-AirframeGimbalNativeNodeForms.py',
    'tools\blueprint\Test-AirframeGimbalNativeNodeForms.py',
    'tools\blueprint\templates\airframe-gimbal-native-node-forms.eddgraph',
    'tools\blueprint\Build-AirframeGimbalSolveGraph.py',
    'tools\blueprint\Test-AirframeGimbalSolveContracts.py',
    'tools\blueprint\snippets\solve-airframe-gimbal-v1.eddgraph',
    'tools\blueprint\snippets\solve-airframe-gimbal-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\solve-airframe-gimbal-v1.eddgraph',
    'tools\unreal\Configure-AirframeGimbalAssembly.py',
    'tools\unreal\Validate-AirframeGimbalRuntime.py',
    'tools\unreal\Validate-AirframePrebakeRuntime.py',
    'tools\unreal\Configure-AirframeDesiredStreamAssembly.py',
    'tools\unreal\Validate-AirframeDesiredStreamRuntime.py',
    'tools\blueprint\Build-SmoothedFlightProfileResetGraph.py',
    'tools\blueprint\Test-SmoothedFlightProfileResetContracts.py',
    'tools\blueprint\snippets\reset-smoothed-flight-profile-v1.eddgraph',
    'tools\blueprint\snippets\reset-smoothed-flight-profile-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-smoothed-flight-profile-v1.eddgraph',
    'tools\blueprint\Build-SmoothedFlightProfileStageGraph.py',
    'tools\blueprint\Test-SmoothedFlightProfileStageContracts.py',
    'tools\blueprint\snippets\stage-smoothed-flight-profile-samples-v1.eddgraph',
    'tools\blueprint\snippets\stage-smoothed-flight-profile-samples-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\stage-smoothed-flight-profile-samples-v1.eddgraph',
    'tools\blueprint\Build-SmoothedFlightProfilePublishGraph.py',
    'tools\blueprint\Test-SmoothedFlightProfilePublishContracts.py',
    'tools\blueprint\snippets\publish-smoothed-flight-profile-v1.eddgraph',
    'tools\blueprint\snippets\publish-smoothed-flight-profile-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\publish-smoothed-flight-profile-v1.eddgraph',
    'tools\blueprint\Build-SmoothedFlightProfileEvaluateGraph.py',
    'tools\blueprint\Test-SmoothedFlightProfileEvaluateContracts.py',
    'tools\blueprint\snippets\evaluate-smoothed-flight-profile-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-smoothed-flight-profile-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\evaluate-smoothed-flight-profile-v1.eddgraph',
    'tools\unreal\Validate-SmoothedFlightProfileRuntime.py',
    'tools\blueprint\Build-FlightProfileResetGraph.py',
    'tools\blueprint\Test-FlightProfileResetContracts.py',
    'tools\blueprint\snippets\reset-flight-profile-state-v1.eddgraph',
    'tools\blueprint\snippets\reset-flight-profile-state-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-flight-profile-state-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileValidationGraph.py',
    'tools\blueprint\Test-FlightProfileValidationContracts.py',
    'tools\blueprint\snippets\validate-flight-profile-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-flight-profile-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-flight-profile-inputs-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileResolverGraph.py',
    'tools\blueprint\Test-FlightProfileResolverContracts.py',
    'tools\blueprint\snippets\resolve-flight-profile-preset-v1.eddgraph',
    'tools\blueprint\snippets\resolve-flight-profile-preset-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\resolve-flight-profile-preset-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileCandidatesGraph.py',
    'tools\blueprint\Test-FlightProfileCandidatesContracts.py',
    'tools\blueprint\snippets\build-flight-profile-candidates-v1.eddgraph',
    'tools\blueprint\snippets\build-flight-profile-candidates-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-flight-profile-candidates-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileCommitGraph.py',
    'tools\blueprint\Test-FlightProfileCommitContracts.py',
    'tools\blueprint\snippets\commit-compiled-flight-profiles-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-flight-profiles-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-compiled-flight-profiles-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileCompileGraph.py',
    'tools\blueprint\Test-FlightProfileCompileContracts.py',
    'tools\blueprint\snippets\compile-flight-profiles-v1.eddgraph',
    'tools\blueprint\snippets\compile-flight-profiles-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-flight-profiles-v1.eddgraph',
    'tools\blueprint\Build-FlightProfileEvaluatorGraph.py',
    'tools\blueprint\Test-FlightProfileEvaluatorContracts.py',
    'tools\blueprint\Inspect-BlueprintFunctionSeam.py',
    'tools\blueprint\snippets\evaluate-compiled-flight-profile-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-compiled-flight-profile-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\evaluate-compiled-flight-profile-v1.eddgraph',
    'tools\unreal\Configure-FlightProfileAssembly.py',
    'tools\unreal\Validate-FlightProfileRuntime.py',
    'tools\unreal\Configure-CinematicPoseAssembly.py',
    'tools\unreal\Validate-CinematicPoseRuntime.py',
    'tools\blueprint\Build-CinematicPoseResetGraph.py',
    'tools\blueprint\Test-CinematicPoseResetContracts.py',
    'tools\blueprint\snippets\reset-cinematic-pose-v1.eddgraph',
    'tools\blueprint\snippets\reset-cinematic-pose-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-cinematic-pose-v1.eddgraph',
    'tools\blueprint\Build-CinematicPoseValidationGraph.py',
    'tools\blueprint\Test-CinematicPoseValidationContracts.py',
    'tools\blueprint\snippets\validate-cinematic-pose-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-cinematic-pose-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-cinematic-pose-inputs-v1.eddgraph',
    'tools\blueprint\Build-CinematicPoseCommitGraph.py',
    'tools\blueprint\Test-CinematicPoseCommitContracts.py',
    'tools\blueprint\snippets\commit-compiled-cinematic-pose-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-cinematic-pose-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-compiled-cinematic-pose-v1.eddgraph',
    'tools\blueprint\Build-CinematicPoseCompileGraph.py',
    'tools\blueprint\Test-CinematicPoseCompileContracts.py',
    'tools\blueprint\snippets\compile-cinematic-pose-v1.eddgraph',
    'tools\blueprint\snippets\compile-cinematic-pose-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-cinematic-pose-v1.eddgraph',
    'tools\blueprint\Build-CinematicPoseEvaluatorGraph.py',
    'tools\blueprint\Test-CinematicPoseEvaluatorContracts.py',
    'tools\blueprint\snippets\evaluate-compiled-cinematic-pose-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-compiled-cinematic-pose-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\evaluate-compiled-cinematic-pose-v1.eddgraph',
    'tools\unreal\Configure-TrajectoryScalarEvaluators.py',
    'tools\unreal\Compile-And-SaveClientDirector.py',
    'tools\unreal\Open-ClientDirectorEditor.py',
    'tools\unreal\Validate-TrajectoryScalarEvaluatorsRuntime.py',
    'tools\blueprint\Build-TrajectoryScalarEvaluatorGraphs.py',
    'tools\blueprint\Test-TrajectoryScalarEvaluatorContracts.py',
    'tools\blueprint\snippets\evaluate-time-profile-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-quintic-scalar-v1.eddgraph',
    'tools\unreal\Configure-TrajectoryVectorEvaluator.py',
    'tools\unreal\Validate-TrajectoryVectorEvaluatorRuntime.py',
    'tools\blueprint\Build-TrajectoryVectorEvaluatorGraph.py',
    'tools\blueprint\Test-TrajectoryVectorEvaluatorContracts.py',
    'tools\blueprint\snippets\evaluate-quintic-vector-v1.eddgraph',
    'tools\blueprint\live-snippets\evaluate-quintic-vector-v1.eddgraph',
    'tools\unreal\Configure-TrajectoryQuaternionEvaluator.py',
    'tools\unreal\Validate-TrajectoryQuaternionEvaluatorRuntime.py',
    'tools\blueprint\Build-TrajectoryQuaternionNativeNodeForms.py',
    'tools\blueprint\Test-TrajectoryQuaternionNativeNodeForms.py',
    'tools\blueprint\templates\trajectory-quaternion-native-node-forms.eddgraph',
    'tools\blueprint\Build-TrajectoryQuaternionEvaluatorGraph.py',
    'tools\blueprint\Test-TrajectoryQuaternionEvaluatorContracts.py',
    'tools\blueprint\snippets\evaluate-spherical-bezier-quaternion-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-spherical-bezier-quaternion-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\evaluate-spherical-bezier-quaternion-v1.eddgraph',
    'tools\unreal\Configure-OrientationCompiler.py',
    'tools\unreal\Configure-OrientationTrackAssembly.py',
    'tools\unreal\Validate-OrientationCompilerRuntime.py',
    'tools\unreal\Validate-OrientationTrackValidationRuntime.py',
    'tools\unreal\Validate-OrientationTrackAlignmentRuntime.py',
    'tools\unreal\Validate-OrientationForwardDeltasRuntime.py',
    'tools\unreal\Validate-OrientationTrackTangentRatesRuntime.py',
    'tools\unreal\Validate-OrientationTrackSegmentsRuntime.py',
    'tools\unreal\Validate-OrientationTrackCommitRuntime.py',
    'tools\unreal\Configure-ArcTableInversion.py',
    'tools\unreal\Validate-ArcTableInversionRuntime.py',
    'tools\unreal\Configure-AdaptiveArcAssembly.py',
    'tools\unreal\Validate-AdaptiveArcBoundaryRuntime.py',
    'tools\unreal\Validate-AdaptiveArcInitializationRuntime.py',
    'tools\unreal\Validate-AdaptiveArcProcessRuntime.py',
    'tools\unreal\Validate-AdaptiveArcCommitRuntime.py',
    'tools\unreal\Validate-AdaptiveArcCompileRuntime.py',
    'tools\unreal\Move-SelectedBlueprintNode.ps1',
    'tools\unreal\Invoke-BlueprintRelativeDrag.ps1',
    'tools\unreal\Configure-PositionRouteAssembly.py',
    'tools\unreal\Validate-PositionRouteResetRuntime.py',
    'tools\unreal\Validate-PositionRouteValidationRuntime.py',
    'tools\unreal\Validate-PositionRouteVelocitiesRuntime.py',
    'tools\unreal\Validate-PositionRouteSegmentsRuntime.py',
    'tools\unreal\Validate-PositionRouteCommitRuntime.py',
    'tools\unreal\Validate-PositionRouteCompileRuntime.py',
    'tools\unreal\Validate-PositionRouteArcSliceRuntime.py',
    'tools\unreal\Validate-PositionRouteEvaluatorRuntime.py',
    'tools\unreal\Open-BlueprintFunctionViaFindResults.ps1',
    'tools\blueprint\Build-OrientationCompilerNativeNodeForms.py',
    'tools\blueprint\Build-OrientationCompilerGraphs.py',
    'tools\blueprint\Test-OrientationCompilerContracts.py',
    'tools\blueprint\Build-OrientationTrackResetGraph.py',
    'tools\blueprint\Test-OrientationTrackResetContracts.py',
    'tools\blueprint\Build-OrientationTrackValidationGraph.py',
    'tools\blueprint\Test-OrientationTrackValidationContracts.py',
    'tools\blueprint\Build-OrientationTrackAlignmentGraph.py',
    'tools\blueprint\Test-OrientationTrackAlignmentContracts.py',
    'tools\blueprint\Build-OrientationForwardDeltasGraph.py',
    'tools\blueprint\Test-OrientationForwardDeltasContracts.py',
    'tools\blueprint\Build-OrientationTrackTangentRatesGraph.py',
    'tools\blueprint\Test-OrientationTrackTangentRatesContracts.py',
    'tools\blueprint\Build-OrientationTrackSegmentsGraph.py',
    'tools\blueprint\Test-OrientationTrackSegmentsContracts.py',
    'tools\blueprint\Build-OrientationTrackCommitGraph.py',
    'tools\blueprint\Test-OrientationTrackCommitContracts.py',
    'tools\blueprint\Build-OrientationTrackCompileGraph.py',
    'tools\blueprint\Test-OrientationTrackCompileContracts.py',
    'tools\blueprint\Build-ArcTableInversionGraph.py',
    'tools\blueprint\Test-ArcTableInversionContracts.py',
    'tools\blueprint\Build-AdaptiveArcResetGraph.py',
    'tools\blueprint\Test-AdaptiveArcResetContracts.py',
    'tools\blueprint\Build-AdaptiveArcValidationGraph.py',
    'tools\blueprint\Test-AdaptiveArcValidationContracts.py',
    'tools\blueprint\Build-AdaptiveArcInitializationGraph.py',
    'tools\blueprint\Test-AdaptiveArcInitializationContracts.py',
    'tools\blueprint\Build-AdaptiveArcProcessGraph.py',
    'tools\blueprint\Test-AdaptiveArcProcessContracts.py',
    'tools\blueprint\Build-AdaptiveArcCommitGraph.py',
    'tools\blueprint\Test-AdaptiveArcCommitContracts.py',
    'tools\blueprint\Build-AdaptiveArcCompileGraph.py',
    'tools\blueprint\Test-AdaptiveArcCompileContracts.py',
    'tools\blueprint\Build-PositionRouteResetGraph.py',
    'tools\blueprint\Test-PositionRouteResetContracts.py',
    'tools\blueprint\Build-PositionRouteValidationGraph.py',
    'tools\blueprint\Test-PositionRouteValidationContracts.py',
    'tools\blueprint\Build-PositionRouteVelocitiesGraph.py',
    'tools\blueprint\Test-PositionRouteVelocitiesContracts.py',
    'tools\blueprint\Build-PositionRouteSegmentsGraph.py',
    'tools\blueprint\Test-PositionRouteSegmentsContracts.py',
    'tools\blueprint\Build-PositionRouteCommitGraph.py',
    'tools\blueprint\Test-PositionRouteCommitContracts.py',
    'tools\blueprint\Build-PositionRouteCompileGraph.py',
    'tools\blueprint\Test-PositionRouteCompileContracts.py',
    'tools\blueprint\Build-PositionRouteArcSliceGraph.py',
    'tools\blueprint\Test-PositionRouteArcSliceContracts.py',
    'tools\blueprint\Build-PositionRouteEvaluatorGraph.py',
    'tools\blueprint\Test-PositionRouteEvaluatorContracts.py',
    'tools\blueprint\templates\adaptive-arc-forloop-node-form.eddgraph',
    'tools\blueprint\templates\adaptive-arc-for-loop-with-break-node-form.eddgraph',
    'tools\blueprint\templates\adaptive-arc-process-node-forms.eddgraph',
    'tools\blueprint\templates\orientation-compiler-native-node-forms.eddgraph',
    'tools\blueprint\snippets\compute-orientation-log-delta-v1.eddgraph',
    'tools\blueprint\snippets\compute-orientation-log-delta-v1-paste.eddgraph',
    'tools\blueprint\snippets\compute-orientation-tangent-rate-v1.eddgraph',
    'tools\blueprint\snippets\compute-orientation-tangent-rate-v1-paste.eddgraph',
    'tools\blueprint\snippets\build-orientation-segment-controls-v1.eddgraph',
    'tools\blueprint\snippets\build-orientation-segment-controls-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compute-orientation-log-delta-v1.eddgraph',
    'tools\blueprint\live-snippets\compute-orientation-tangent-rate-v1.eddgraph',
    'tools\blueprint\live-snippets\build-orientation-segment-controls-v1.eddgraph',
    'tools\blueprint\snippets\reset-orientation-track-candidate-v1.eddgraph',
    'tools\blueprint\snippets\reset-orientation-track-candidate-v1-paste.eddgraph',
    'tools\blueprint\snippets\validate-orientation-track-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-orientation-track-inputs-v1-paste.eddgraph',
    'tools\blueprint\snippets\align-orientation-waypoints-v1.eddgraph',
    'tools\blueprint\snippets\align-orientation-waypoints-v1-paste.eddgraph',
    'tools\blueprint\snippets\compute-orientation-forward-deltas-v1.eddgraph',
    'tools\blueprint\snippets\compute-orientation-forward-deltas-v1-paste.eddgraph',
    'tools\blueprint\snippets\compute-orientation-track-tangent-rates-v1.eddgraph',
    'tools\blueprint\snippets\compute-orientation-track-tangent-rates-v1-paste.eddgraph',
    'tools\blueprint\snippets\build-orientation-track-segments-v1.eddgraph',
    'tools\blueprint\snippets\build-orientation-track-segments-v1-paste.eddgraph',
    'tools\blueprint\snippets\commit-compiled-orientation-track-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-orientation-track-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-compiled-orientation-track-v1.eddgraph',
    'tools\blueprint\snippets\compile-orientation-track-v1.eddgraph',
    'tools\blueprint\snippets\compile-orientation-track-v1-paste.eddgraph',
    'tools\blueprint\snippets\invert-arc-length-table-v1.eddgraph',
    'tools\blueprint\snippets\invert-arc-length-table-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\invert-arc-length-table-v1.eddgraph',
    'tools\blueprint\snippets\reset-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\reset-adaptive-arc-build-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\validate-adaptive-arc-build-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-adaptive-arc-build-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-adaptive-arc-build-inputs-v1.eddgraph',
    'tools\blueprint\snippets\initialize-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\initialize-adaptive-arc-build-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\initialize-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\process-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\process-adaptive-arc-build-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\process-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\commit-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\commit-adaptive-arc-build-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-adaptive-arc-build-v1.eddgraph',
    'tools\blueprint\snippets\build-adaptive-arc-table-v1.eddgraph',
    'tools\blueprint\snippets\build-adaptive-arc-table-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-adaptive-arc-table-v1.eddgraph',
    'tools\blueprint\snippets\reset-position-route-candidate-v1.eddgraph',
    'tools\blueprint\snippets\reset-position-route-candidate-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-position-route-candidate-v1.eddgraph',
    'tools\blueprint\snippets\validate-position-route-inputs-v1.eddgraph',
    'tools\blueprint\snippets\validate-position-route-inputs-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\validate-position-route-inputs-v1.eddgraph',
    'tools\blueprint\snippets\compute-position-route-velocities-v1.eddgraph',
    'tools\blueprint\snippets\compute-position-route-velocities-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compute-position-route-velocities-v1.eddgraph',
    'tools\blueprint\snippets\build-position-route-segments-v1.eddgraph',
    'tools\blueprint\snippets\build-position-route-segments-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\build-position-route-segments-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-position-route-v1.eddgraph',
    'tools\blueprint\snippets\commit-compiled-position-route-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\commit-compiled-position-route-v1.eddgraph',
    'tools\blueprint\snippets\compile-position-route-v1.eddgraph',
    'tools\blueprint\snippets\compile-position-route-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\compile-position-route-v1.eddgraph',
    'tools\blueprint\snippets\stage-position-route-arc-slice-v1.eddgraph',
    'tools\blueprint\snippets\stage-position-route-arc-slice-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\stage-position-route-arc-slice-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-compiled-position-route-v1.eddgraph',
    'tools\blueprint\snippets\evaluate-compiled-position-route-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\evaluate-compiled-position-route-v1.eddgraph',
    'tools\blueprint\live-snippets\compile-orientation-track-v1.eddgraph',
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
    'tools\persistence\alternating_snapshot_oracle.py',
    'tools\persistence\test_alternating_snapshot_oracle.py',
    'tools\repository\blueprint_repository_service_schema.json',
    'tools\repository\test_blueprint_repository_service_schema.py',
    'tools\blueprint\Build-RepositoryCoreGraphs.py',
    'tools\blueprint\Build-RepositoryPrivateDraftLoadGraph.py',
    'tools\blueprint\Build-RepositoryPrivateCreateGraph.py',
    'tools\blueprint\Build-RepositoryPrivateSaveGraph.py',
    'tools\blueprint\Build-RepositoryPrivateListGraph.py',
    'tools\blueprint\Build-RepositoryPublicListGraph.py',
    'tools\blueprint\Build-RepositoryPublishedFetchGraph.py',
    'tools\blueprint\Build-RepositoryClonePublishedGraph.py',
    'tools\blueprint\Build-RepositoryPrivateDeleteGraph.py',
    'tools\blueprint\Build-RepositoryPublishDraftGraph.py',
    'tools\blueprint\Build-RepositoryUnpublishGraph.py',
    'tools\blueprint\Build-RepositoryJsonMissingNodeProbe.py',
    'tools\blueprint\Build-RepositoryDecoderNativeNodeProbe.py',
    'tools\blueprint\Test-RepositoryJsonNodeForms.py',
    'tools\blueprint\Test-RepositoryDecoderNativeNodeForms.py',
    'tools\blueprint\Test-RepositoryCodecMathNodeForms.py',
    'tools\blueprint\Test-RepositoryCodecBreakQuatNodeForm.py',
    'tools\blueprint\Test-RepositoryCodecTransformNodeForms.py',
    'tools\blueprint\Build-RepositoryDocumentEncoderGraphs.py',
    'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py',
    'tools\blueprint\Build-RepositoryDocumentDecoderGraphs.py',
    'tools\blueprint\Test-RepositoryDocumentDecoderContracts.py',
    'tools\blueprint\Build-RepositoryRecordEncoderGraphs.py',
    'tools\blueprint\Test-RepositoryRecordEncoderContracts.py',
    'tools\blueprint\Build-RepositoryRecordDecoderGraphs.py',
    'tools\blueprint\Test-RepositoryRecordDecoderContracts.py',
    'tools\blueprint\Build-RepositoryValidationGraphs.py',
    'tools\blueprint\Test-RepositoryValidationContracts.py',
    'tools\blueprint\Build-RepositoryPersistenceStateGraphs.py',
    'tools\blueprint\Test-RepositoryPersistenceStateContracts.py',
    'tools\blueprint\Build-RepositoryPersistenceWriterGraphs.py',
    'tools\blueprint\Test-RepositoryPersistenceWriterContracts.py',
    'tools\blueprint\Build-RepositorySaveGameAdapterGraphs.py',
    'tools\blueprint\Test-RepositorySaveGameAdapterContracts.py',
    'tools\blueprint\Build-RepositoryRecoverySelectionGraphs.py',
    'tools\blueprint\Test-RepositoryRecoverySelectionContracts.py',
    'tools\blueprint\Build-RepositoryTombstoneRecoveryGraphs.py',
    'tools\blueprint\Test-RepositoryTombstoneRecoveryContracts.py',
    'tools\blueprint\Build-RepositoryRecordRecoveryGraphs.py',
    'tools\blueprint\Test-RepositoryRecordRecoveryContracts.py',
    'tools\blueprint\templates\repository-string-trim-node-form.eddgraph',
    'tools\unreal\Invoke-EnhancedEditorInput.ps1',
    'tools\unreal\Export-BlueprintFunctions.ps1',
    'tools\blueprint\Test-RepositorySaveGameNodeForms.py',
    'tools\blueprint\Test-RepositoryCoreContracts.py',
    'tools\blueprint\Test-RepositoryPrivateDraftLoadContracts.py',
    'tools\blueprint\Test-RepositoryPrivateCreateContracts.py',
    'tools\blueprint\Test-RepositoryPrivateSaveContracts.py',
    'tools\blueprint\Test-RepositoryPrivateListContracts.py',
    'tools\blueprint\Test-RepositoryPublicListContracts.py',
    'tools\blueprint\Test-RepositoryPublishedFetchContracts.py',
    'tools\blueprint\Test-RepositoryClonePublishedContracts.py',
    'tools\blueprint\Test-RepositoryPrivateDeleteContracts.py',
    'tools\blueprint\Test-RepositoryPublishDraftContracts.py',
    'tools\blueprint\Test-RepositoryUnpublishContracts.py',
    'tools\unreal\Generate-MvpScaffold.py',
    'tools\blueprint\Export-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Set-BlueprintGraphClipboard.ps1',
    'tools\blueprint\Test-BlueprintGraphSnippet.ps1',
    'tools\blueprint\Test-BlueprintGraphContracts.ps1',
    'tools\blueprint\Build-RollInputGraph.py',
    'tools\blueprint\templates\horizon-node-forms.eddgraph',
    'tools\blueprint\templates\repository-codec-break-quat-node-form.eddgraph',
    'tools\blueprint\templates\repository-decoder-native-node-forms.eddgraph',
    'tools\blueprint\templates\repository-savegame-native-node-forms.eddgraph',
    'tools\blueprint\templates\repository-savegame-storage-node-forms.eddgraph',
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
    'tools\blueprint\templates\repository-codec-transform-node-forms.eddgraph',
    'tools\blueprint\templates\repository-codec-vector-node-forms.eddgraph',
    'tools\blueprint\templates\repository-codec-array-node-forms.eddgraph',
    'tools\blueprint\snippets\toggle-input.eddgraph',
    'tools\blueprint\snippets\toggle-state.eddgraph',
    'tools\blueprint\snippets\enter-drone-mode.eddgraph',
    'tools\blueprint\snippets\encode-waypoint-v1.eddgraph',
    'tools\blueprint\snippets\encode-segment-v1.eddgraph',
    'tools\blueprint\snippets\encode-document-v1.eddgraph',
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
    'tools\blueprint\snippets\load-draft-v1.eddgraph',
    'tools\blueprint\snippets\load-draft-v1-paste.eddgraph',
    'tools\blueprint\snippets\fetch-published-revision-v1.eddgraph',
    'tools\blueprint\snippets\fetch-published-revision-v1-paste.eddgraph',
    'tools\blueprint\snippets\clone-published-v1.eddgraph',
    'tools\blueprint\snippets\clone-published-v1-paste.eddgraph',
    'tools\blueprint\snippets\create-private-flypath-v1.eddgraph',
    'tools\blueprint\snippets\create-private-flypath-v1-paste.eddgraph',
    'tools\blueprint\snippets\save-draft-v1.eddgraph',
    'tools\blueprint\snippets\save-draft-v1-paste.eddgraph',
    'tools\blueprint\snippets\delete-flypath-v1.eddgraph',
    'tools\blueprint\snippets\delete-flypath-v1-paste.eddgraph',
    'tools\blueprint\live-snippets\reset-repository-result-v1.eddgraph',
    'tools\blueprint\live-snippets\find-record-index-v1.eddgraph',
    'tools\blueprint\live-snippets\load-draft-v1.eddgraph',
    'tools\blueprint\live-snippets\fetch-published-revision-v1.eddgraph',
    'tools\blueprint\live-snippets\clone-published-v1.eddgraph',
    'tools\blueprint\live-snippets\create-private-flypath-v1.eddgraph',
    'tools\blueprint\live-snippets\save-draft-v1.eddgraph',
    'tools\blueprint\live-snippets\delete-flypath-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-waypoint-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-segment-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-document-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-record-published-fields-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-record-source-attribution-v1.eddgraph',
    'tools\blueprint\live-snippets\encode-record-v1.eddgraph',
    'tools\blueprint\live-snippets\decode-record-published-fields-v1.eddgraph',
    'tools\blueprint\live-snippets\decode-record-source-attribution-v1.eddgraph',
    'tools\blueprint\live-snippets\decode-record-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-waypoint-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-segment-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-document-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-record-published-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-record-source-attribution-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-record-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-repository-state-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-storage-headers-v1.eddgraph',
    'tools\blueprint\live-snippets\prepare-persistence-candidate-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-persistence-candidate-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-persistence-write-v1.eddgraph',
    'tools\blueprint\live-snippets\build-persistence-write-storage-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-persistence-write-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-persistence-write-v1.eddgraph',
    'tools\blueprint\live-snippets\persist-repository-v1.eddgraph',
    'tools\blueprint\live-snippets\read-repository-storage-slot-a-v1.eddgraph',
    'tools\blueprint\live-snippets\read-repository-storage-slot-b-v1.eddgraph',
    'tools\blueprint\live-snippets\read-repository-storage-slots-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-recovery-selection-v1.eddgraph',
    'tools\blueprint\live-snippets\compare-recovery-string-arrays-v1.eddgraph',
    'tools\blueprint\live-snippets\compare-equal-generation-storage-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-recovery-a-only-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-recovery-b-only-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-recovery-a-newer-v1.eddgraph',
    'tools\blueprint\live-snippets\stage-recovery-b-newer-v1.eddgraph',
    'tools\blueprint\live-snippets\select-repository-recovery-order-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-recovery-tombstones-v1.eddgraph',
    'tools\blueprint\live-snippets\find-recovery-string-index-v1.eddgraph',
    'tools\blueprint\live-snippets\validate-recovery-tombstone-channel-v1.eddgraph',
    'tools\blueprint\live-snippets\merge-recovery-tombstones-v1.eddgraph',
    'tools\blueprint\live-snippets\reset-recovery-records-v1.eddgraph',
    'tools\blueprint\live-snippets\decode-validate-recovery-envelope-v1.eddgraph',
    'tools\blueprint\live-snippets\scan-recovery-record-identity-v1.eddgraph',
    'tools\blueprint\live-snippets\append-recovery-record-if-new-v1.eddgraph',
    'tools\blueprint\live-snippets\try-merge-recovery-record-v1.eddgraph',
    'tools\blueprint\live-snippets\recover-record-channel-v1.eddgraph',
    'tools\blueprint\live-snippets\recover-repository-records-v1.eddgraph',
    'tools\blueprint\live-snippets\commit-recovered-repository-v1.eddgraph',
    'tools\blueprint\live-snippets\load-repository-v1.eddgraph',
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

$editorInputPath = Join-Path $ProjectRoot 'tools\unreal\Invoke-EnhancedEditorInput.ps1'
$editorInputSource = [IO.File]::ReadAllText($editorInputPath)
if ($editorInputSource -notmatch 'IsIconic\(hWnd\)') {
    throw 'Editor input helper must test IsIconic before restoring a window.'
}
if ($editorInputSource -notmatch 'if \(IsIconic\(hWnd\)\) ShowWindow\(hWnd, 9\);') {
    throw 'Editor input helper must preserve maximized windows instead of unconditionally restoring them.'
}
if ($editorInputSource -notmatch "ValidateSet\('Left', 'Right'\)") {
    throw 'Editor input helper must expose an explicit right-click mode.'
}
if ($editorInputSource -notmatch "ClickButton -eq 'Right'") {
    throw 'Editor input helper must map right-click to the native right mouse flags.'
}
if ($editorInputSource -notmatch "ValidateSet\('None', 'Alt', 'Control', 'Shift'\)") {
    throw 'Editor input helper must expose modifier-held click gestures.'
}
if ($editorInputSource -notmatch 'keybd_event\(\$modifierKey, 0, 0x0002') {
    throw 'Editor input helper must release held click modifiers in a finally block.'
}
if ($editorInputSource -notmatch '\[switch\]\$PreserveForeground' -or
    $editorInputSource -notmatch 'if \(-not \$PreserveForeground\)') {
    throw 'Editor input helper must support popup-safe foreground preservation.'
}

$windowScreenshotPath = Join-Path $ProjectRoot 'tools\unreal\Save-WindowScreenshot.ps1'
$windowScreenshotSource = [IO.File]::ReadAllText($windowScreenshotPath)
if ($windowScreenshotSource -notmatch '\[switch\]\$PreserveForeground' -or
    $windowScreenshotSource -notmatch 'if \(-not \$PreserveForeground\)') {
    throw 'Window screenshot helper must support popup-safe foreground preservation.'
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

$repositorySaveGameNativeForms = Join-Path $ProjectRoot 'tools\blueprint\templates\repository-savegame-native-node-forms.eddgraph'
$repositorySaveGameStorageForms = Join-Path $ProjectRoot 'tools\blueprint\templates\repository-savegame-storage-node-forms.eddgraph'
foreach ($graph in @($repositorySaveGameNativeForms, $repositorySaveGameStorageForms)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositorySaveGameNodeForms.py') `
    --native $repositorySaveGameNativeForms `
    --storage $repositorySaveGameStorageForms
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame node-form contracts failed with exit code $LASTEXITCODE."
}

$scratchRoot = if ($env:REDLEAF_SCRATCH_DIR) {
    $env:REDLEAF_SCRATCH_DIR
} else {
    [IO.Path]::GetTempPath()
}
& (Join-Path $ProjectRoot 'tools\unreal\Test-EnhancedEditorRemoteExecutionConfig.ps1') `
    -ProjectRoot $ProjectRoot `
    -ScratchRoot $scratchRoot
if ($LASTEXITCODE -ne 0) {
    throw "Enhanced editor remote-execution config contracts failed with exit code $LASTEXITCODE."
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
& python (Join-Path $ProjectRoot 'tools\trajectory\test_cinematic_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic trajectory reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_orientation_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic orientation reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_orientation_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Orientation Blueprint assembly-schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_arc_table_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Arc-table Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_adaptive_arc_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Adaptive arc Blueprint assembly-schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_position_route_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Position-route Blueprint assembly-schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_cinematic_pose_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic pose composition reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_cinematic_pose_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic pose Blueprint composition-schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_flight_profile_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Flight-profile reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_flight_profile_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Flight-profile Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_smoothed_flight_profile_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Smoothed flight-profile reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_smoothed_flight_profile_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Smoothed flight-profile Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_gimbal_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe/gimbal desired-pose reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_gimbal_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe/gimbal Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_gimbal_prebake_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe/gimbal fixed-step prebake reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_gimbal_prebake_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe/gimbal fixed-step prebake Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_desired_stream_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe desired-stream reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_desired_stream_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe desired-stream Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_source_sampling_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe source-sampling reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_airframe_source_sampling_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Airframe source-sampling Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_compiled_document_source_adapter_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Compiled-document source-adapter reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_compiled_document_source_adapter_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Compiled-document source-adapter Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_scalar_track_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera scalar-track reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_scalar_track_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera scalar-track Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_channel_assembly_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera channel-assembly reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_channel_assembly_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera channel-assembly Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_engine_application_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_engine_application_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_engine_property_probe_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-property probe contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_configure_camera_engine_application.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine live-configurator contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_focus_helper_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera focus-helper reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_focus_helper_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera focus-helper Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_dof_diagnostics_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera DOF diagnostic reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_dof_diagnostics_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera DOF diagnostic Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_dolly_zoom_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera dolly-zoom reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_dolly_zoom_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera dolly-zoom Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_base_look_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera base-look reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_base_look_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera base-look Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_viewer_comfort_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera viewer-comfort reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_viewer_comfort_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera viewer-comfort Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_operator_override_reference.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera operator-override reference contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\trajectory\test_camera_operator_override_blueprint_schema.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera operator-override Blueprint schema contracts failed with exit code $LASTEXITCODE."
}
$cameraOperatorRoot = Join-Path $scratchRoot ("edd-camera-operator-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraOperatorRoot -Force | Out-Null
$cameraOperatorReset = Join-Path $cameraOperatorRoot 'reset-camera-operator-override-step-v1.eddgraph'
$cameraOperatorResetPaste = Join-Path $cameraOperatorRoot 'reset-camera-operator-override-step-v1-paste.eddgraph'
$cameraOperatorResetRepeat = Join-Path $cameraOperatorRoot 'reset-camera-operator-override-step-v1-repeat.eddgraph'
$cameraOperatorResetRepeatPaste = Join-Path $cameraOperatorRoot 'reset-camera-operator-override-step-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraOperatorReset,$cameraOperatorResetPaste),@($cameraOperatorResetRepeat,$cameraOperatorResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraOperatorOverrideResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera operator reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraOperatorReset,$cameraOperatorResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-operator-override-step-v1.eddgraph')),
    @($cameraOperatorResetPaste,$cameraOperatorResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-operator-override-step-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera operator reset generation is not byte deterministic.'
    }
}
foreach ($graph in @($cameraOperatorReset,$cameraOperatorResetPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera operator reset link integrity failed with exit code $LASTEXITCODE." }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorReset
if ($LASTEXITCODE -ne 0) { throw "Camera operator reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera operator reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraOperatorValidation = Join-Path $cameraOperatorRoot 'validate-camera-operator-override-inputs-v1.eddgraph'
$cameraOperatorValidationPaste = Join-Path $cameraOperatorRoot 'validate-camera-operator-override-inputs-v1-paste.eddgraph'
$cameraOperatorValidationRepeat = Join-Path $cameraOperatorRoot 'validate-camera-operator-override-inputs-v1-repeat.eddgraph'
$cameraOperatorValidationRepeatPaste = Join-Path $cameraOperatorRoot 'validate-camera-operator-override-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(
    @($cameraOperatorValidation,$cameraOperatorValidationPaste),
    @($cameraOperatorValidationRepeat,$cameraOperatorValidationRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraOperatorOverrideValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera operator validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraOperatorValidation,$cameraOperatorValidationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-operator-override-inputs-v1.eddgraph')),
    @($cameraOperatorValidationPaste,$cameraOperatorValidationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-operator-override-inputs-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera operator validation generation is not byte deterministic.'
    }
}
foreach ($graph in @($cameraOperatorValidation,$cameraOperatorValidationPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera operator validation link integrity failed with exit code $LASTEXITCODE." }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorValidation
if ($LASTEXITCODE -ne 0) { throw "Camera operator validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera operator validation paste contracts failed with exit code $LASTEXITCODE." }
$cameraOperatorTranslation = Join-Path $cameraOperatorRoot 'build-camera-operator-translation-v1.eddgraph'
$cameraOperatorTranslationPaste = Join-Path $cameraOperatorRoot 'build-camera-operator-translation-v1-paste.eddgraph'
$cameraOperatorTranslationRepeat = Join-Path $cameraOperatorRoot 'build-camera-operator-translation-v1-repeat.eddgraph'
$cameraOperatorTranslationRepeatPaste = Join-Path $cameraOperatorRoot 'build-camera-operator-translation-v1-repeat-paste.eddgraph'
foreach ($pair in @(
    @($cameraOperatorTranslation,$cameraOperatorTranslationPaste),
    @($cameraOperatorTranslationRepeat,$cameraOperatorTranslationRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraOperatorOverrideTranslationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera operator translation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraOperatorTranslation,$cameraOperatorTranslationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-operator-translation-v1.eddgraph')),
    @($cameraOperatorTranslationPaste,$cameraOperatorTranslationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-operator-translation-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera operator translation generation is not byte deterministic.'
    }
}
foreach ($graph in @($cameraOperatorTranslation,$cameraOperatorTranslationPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera operator translation link integrity failed with exit code $LASTEXITCODE." }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideTranslationContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorTranslation
if ($LASTEXITCODE -ne 0) { throw "Camera operator translation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraOperatorOverrideTranslationContracts.py') `
    --project-root $ProjectRoot --graph $cameraOperatorTranslationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera operator translation paste contracts failed with exit code $LASTEXITCODE." }
$cameraDollyRoot = Join-Path $scratchRoot ("edd-camera-dolly-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraDollyRoot -Force | Out-Null
$cameraDollyReset = Join-Path $cameraDollyRoot 'reset-camera-dolly-zoom-v1.eddgraph'
$cameraDollyResetPaste = Join-Path $cameraDollyRoot 'reset-camera-dolly-zoom-v1-paste.eddgraph'
$cameraDollyResetRepeat = Join-Path $cameraDollyRoot 'reset-camera-dolly-zoom-v1-repeat.eddgraph'
$cameraDollyResetRepeatPaste = Join-Path $cameraDollyRoot 'reset-camera-dolly-zoom-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDollyReset,$cameraDollyResetPaste),@($cameraDollyResetRepeat,$cameraDollyResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDollyZoomResetGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera dolly reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDollyReset,$cameraDollyResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-dolly-zoom-v1.eddgraph')),
    @($cameraDollyResetPaste,$cameraDollyResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-dolly-zoom-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera dolly reset generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDollyReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomResetContracts.py') --project-root $ProjectRoot --graph $cameraDollyReset
if ($LASTEXITCODE -ne 0) { throw "Camera dolly reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomResetContracts.py') --project-root $ProjectRoot --graph $cameraDollyResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera dolly reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraDollyValidation = Join-Path $cameraDollyRoot 'validate-camera-dolly-zoom-inputs-v1.eddgraph'
$cameraDollyValidationPaste = Join-Path $cameraDollyRoot 'validate-camera-dolly-zoom-inputs-v1-paste.eddgraph'
$cameraDollyValidationRepeat = Join-Path $cameraDollyRoot 'validate-camera-dolly-zoom-inputs-v1-repeat.eddgraph'
$cameraDollyValidationRepeatPaste = Join-Path $cameraDollyRoot 'validate-camera-dolly-zoom-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDollyValidation,$cameraDollyValidationPaste),@($cameraDollyValidationRepeat,$cameraDollyValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDollyZoomValidationGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera dolly validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDollyValidation,$cameraDollyValidationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-dolly-zoom-inputs-v1.eddgraph')),
    @($cameraDollyValidationPaste,$cameraDollyValidationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-dolly-zoom-inputs-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera dolly validation generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDollyValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomValidationContracts.py') --project-root $ProjectRoot --graph $cameraDollyValidation
if ($LASTEXITCODE -ne 0) { throw "Camera dolly validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomValidationContracts.py') --project-root $ProjectRoot --graph $cameraDollyValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera dolly validation paste contracts failed with exit code $LASTEXITCODE." }
$cameraDollyCandidates = Join-Path $cameraDollyRoot 'build-camera-dolly-zoom-candidates-v1.eddgraph'
$cameraDollyCandidatesPaste = Join-Path $cameraDollyRoot 'build-camera-dolly-zoom-candidates-v1-paste.eddgraph'
$cameraDollyCandidatesRepeat = Join-Path $cameraDollyRoot 'build-camera-dolly-zoom-candidates-v1-repeat.eddgraph'
$cameraDollyCandidatesRepeatPaste = Join-Path $cameraDollyRoot 'build-camera-dolly-zoom-candidates-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDollyCandidates,$cameraDollyCandidatesPaste),@($cameraDollyCandidatesRepeat,$cameraDollyCandidatesRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDollyZoomCandidatesGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera dolly candidate generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDollyCandidates,$cameraDollyCandidatesRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-dolly-zoom-candidates-v1.eddgraph')),
    @($cameraDollyCandidatesPaste,$cameraDollyCandidatesRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-dolly-zoom-candidates-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera dolly candidate generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDollyCandidates
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraDollyCandidates
if ($LASTEXITCODE -ne 0) { throw "Camera dolly candidate full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraDollyCandidatesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera dolly candidate paste contracts failed with exit code $LASTEXITCODE." }
$cameraDollyCommit = Join-Path $cameraDollyRoot 'commit-camera-dolly-zoom-v1.eddgraph'
$cameraDollyCommitPaste = Join-Path $cameraDollyRoot 'commit-camera-dolly-zoom-v1-paste.eddgraph'
$cameraDollyCommitRepeat = Join-Path $cameraDollyRoot 'commit-camera-dolly-zoom-v1-repeat.eddgraph'
$cameraDollyCommitRepeatPaste = Join-Path $cameraDollyRoot 'commit-camera-dolly-zoom-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDollyCommit,$cameraDollyCommitPaste),@($cameraDollyCommitRepeat,$cameraDollyCommitRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDollyZoomCommitGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera dolly commit generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDollyCommit,$cameraDollyCommitRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-dolly-zoom-v1.eddgraph')),
    @($cameraDollyCommitPaste,$cameraDollyCommitRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-dolly-zoom-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera dolly commit generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDollyCommit
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCommitContracts.py') --project-root $ProjectRoot --graph $cameraDollyCommit
if ($LASTEXITCODE -ne 0) { throw "Camera dolly commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCommitContracts.py') --project-root $ProjectRoot --graph $cameraDollyCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera dolly commit paste contracts failed with exit code $LASTEXITCODE." }
$cameraDollyCompile = Join-Path $cameraDollyRoot 'compile-camera-dolly-zoom-v1.eddgraph'
$cameraDollyCompilePaste = Join-Path $cameraDollyRoot 'compile-camera-dolly-zoom-v1-paste.eddgraph'
$cameraDollyCompileRepeat = Join-Path $cameraDollyRoot 'compile-camera-dolly-zoom-v1-repeat.eddgraph'
$cameraDollyCompileRepeatPaste = Join-Path $cameraDollyRoot 'compile-camera-dolly-zoom-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDollyCompile,$cameraDollyCompilePaste),@($cameraDollyCompileRepeat,$cameraDollyCompileRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDollyZoomCompileGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera dolly compile generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDollyCompile,$cameraDollyCompileRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-dolly-zoom-v1.eddgraph')),
    @($cameraDollyCompilePaste,$cameraDollyCompileRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-dolly-zoom-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera dolly compile generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDollyCompile
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCompileContracts.py') --project-root $ProjectRoot --graph $cameraDollyCompile
if ($LASTEXITCODE -ne 0) { throw "Camera dolly compile full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDollyZoomCompileContracts.py') --project-root $ProjectRoot --graph $cameraDollyCompilePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera dolly compile paste contracts failed with exit code $LASTEXITCODE." }
foreach ($generatedGraph in @(
    $cameraDollyReset,$cameraDollyResetPaste,
    $cameraDollyValidation,$cameraDollyValidationPaste,
    $cameraDollyCandidates,$cameraDollyCandidatesPaste,
    $cameraDollyCommit,$cameraDollyCommitPaste,
    $cameraDollyCompile,$cameraDollyCompilePaste
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $generatedGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Generated camera dolly link integrity failed for $generatedGraph with exit code $LASTEXITCODE."
    }
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_dolly_zoom_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera dolly zoom live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraDollyLiveContracts = @(
    @('reset-camera-dolly-zoom-v1.eddgraph', 'Test-CameraDollyZoomResetContracts.py', $cameraDollyReset),
    @('validate-camera-dolly-zoom-inputs-v1.eddgraph', 'Test-CameraDollyZoomValidationContracts.py', $cameraDollyValidation),
    @('build-camera-dolly-zoom-candidates-v1.eddgraph', 'Test-CameraDollyZoomCandidatesContracts.py', $cameraDollyCandidates),
    @('commit-camera-dolly-zoom-v1.eddgraph', 'Test-CameraDollyZoomCommitContracts.py', $cameraDollyCommit),
    @('compile-camera-dolly-zoom-v1.eddgraph', 'Test-CameraDollyZoomCompileContracts.py', $cameraDollyCompile)
)
foreach ($liveContract in $cameraDollyLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera dolly link integrity failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphTopologyMatch.py') `
        --project-root $ProjectRoot --expected $liveContract[2] --actual $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera dolly topology changed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera dolly graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
$cameraLookRoot = Join-Path $scratchRoot ("edd-camera-look-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraLookRoot -Force | Out-Null
$cameraLookReset = Join-Path $cameraLookRoot 'reset-camera-look-composition-v1.eddgraph'
$cameraLookResetPaste = Join-Path $cameraLookRoot 'reset-camera-look-composition-v1-paste.eddgraph'
$cameraLookResetRepeat = Join-Path $cameraLookRoot 'reset-camera-look-composition-v1-repeat.eddgraph'
$cameraLookResetRepeatPaste = Join-Path $cameraLookRoot 'reset-camera-look-composition-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookReset,$cameraLookResetPaste),@($cameraLookResetRepeat,$cameraLookResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookReset,$cameraLookResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-look-composition-v1.eddgraph')),
    @($cameraLookResetPaste,$cameraLookResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-look-composition-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look reset generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookReset
if ($LASTEXITCODE -ne 0) { throw "Camera base-look reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look reset paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookReset,$cameraLookResetPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look reset link integrity failed with exit code $LASTEXITCODE." }
}
$cameraLookValidation = Join-Path $cameraLookRoot 'validate-camera-look-inputs-v1.eddgraph'
$cameraLookValidationPaste = Join-Path $cameraLookRoot 'validate-camera-look-inputs-v1-paste.eddgraph'
$cameraLookValidationRepeat = Join-Path $cameraLookRoot 'validate-camera-look-inputs-v1-repeat.eddgraph'
$cameraLookValidationRepeatPaste = Join-Path $cameraLookRoot 'validate-camera-look-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookValidation,$cameraLookValidationPaste),@($cameraLookValidationRepeat,$cameraLookValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookValidation,$cameraLookValidationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-look-inputs-v1.eddgraph')),
    @($cameraLookValidationPaste,$cameraLookValidationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-look-inputs-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look validation generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookValidation
if ($LASTEXITCODE -ne 0) { throw "Camera base-look validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look validation paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookValidation,$cameraLookValidationPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look validation link integrity failed with exit code $LASTEXITCODE." }
}
$cameraLookBase = Join-Path $cameraLookRoot 'build-camera-look-base-values-v1.eddgraph'
$cameraLookBasePaste = Join-Path $cameraLookRoot 'build-camera-look-base-values-v1-paste.eddgraph'
$cameraLookBaseRepeat = Join-Path $cameraLookRoot 'build-camera-look-base-values-v1-repeat.eddgraph'
$cameraLookBaseRepeatPaste = Join-Path $cameraLookRoot 'build-camera-look-base-values-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookBase,$cameraLookBasePaste),@($cameraLookBaseRepeat,$cameraLookBaseRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookBaseValuesGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look value generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookBase,$cameraLookBaseRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-look-base-values-v1.eddgraph')),
    @($cameraLookBasePaste,$cameraLookBaseRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-look-base-values-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look value generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookBase
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookBaseValuesContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookBase
if ($LASTEXITCODE -ne 0) { throw "Camera base-look value full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookBaseValuesContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookBasePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look value paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookBase,$cameraLookBasePaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look value link integrity failed with exit code $LASTEXITCODE." }
}
$cameraLookOverrides = Join-Path $cameraLookRoot 'apply-camera-look-authored-overrides-v1.eddgraph'
$cameraLookOverridesPaste = Join-Path $cameraLookRoot 'apply-camera-look-authored-overrides-v1-paste.eddgraph'
$cameraLookOverridesRepeat = Join-Path $cameraLookRoot 'apply-camera-look-authored-overrides-v1-repeat.eddgraph'
$cameraLookOverridesRepeatPaste = Join-Path $cameraLookRoot 'apply-camera-look-authored-overrides-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookOverrides,$cameraLookOverridesPaste),@($cameraLookOverridesRepeat,$cameraLookOverridesRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookOverridesGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look override generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookOverrides,$cameraLookOverridesRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-camera-look-authored-overrides-v1.eddgraph')),
    @($cameraLookOverridesPaste,$cameraLookOverridesRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-camera-look-authored-overrides-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look override generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookOverrides
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookOverridesContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookOverrides
if ($LASTEXITCODE -ne 0) { throw "Camera base-look override full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookOverridesContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookOverridesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look override paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookOverrides,$cameraLookOverridesPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look override link integrity failed with exit code $LASTEXITCODE." }
}
$cameraLookCommit = Join-Path $cameraLookRoot 'commit-camera-look-composition-v1.eddgraph'
$cameraLookCommitPaste = Join-Path $cameraLookRoot 'commit-camera-look-composition-v1-paste.eddgraph'
$cameraLookCommitRepeat = Join-Path $cameraLookRoot 'commit-camera-look-composition-v1-repeat.eddgraph'
$cameraLookCommitRepeatPaste = Join-Path $cameraLookRoot 'commit-camera-look-composition-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookCommit,$cameraLookCommitPaste),@($cameraLookCommitRepeat,$cameraLookCommitRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookCommitGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look commit generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookCommit,$cameraLookCommitRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-look-composition-v1.eddgraph')),
    @($cameraLookCommitPaste,$cameraLookCommitRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-look-composition-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look commit generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookCommit
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookCommit
if ($LASTEXITCODE -ne 0) { throw "Camera base-look commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look commit paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookCommit,$cameraLookCommitPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look commit link integrity failed with exit code $LASTEXITCODE." }
}
$cameraLookCompose = Join-Path $cameraLookRoot 'compose-camera-look-v1.eddgraph'
$cameraLookComposePaste = Join-Path $cameraLookRoot 'compose-camera-look-v1-paste.eddgraph'
$cameraLookComposeRepeat = Join-Path $cameraLookRoot 'compose-camera-look-v1-repeat.eddgraph'
$cameraLookComposeRepeatPaste = Join-Path $cameraLookRoot 'compose-camera-look-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraLookCompose,$cameraLookComposePaste),@($cameraLookComposeRepeat,$cameraLookComposeRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraBaseLookComposeGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look compose generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraLookCompose,$cameraLookComposeRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compose-camera-look-v1.eddgraph')),
    @($cameraLookComposePaste,$cameraLookComposeRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compose-camera-look-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera base-look compose generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraLookCompose
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookComposeContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookCompose
if ($LASTEXITCODE -ne 0) { throw "Camera base-look compose full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraBaseLookComposeContracts.py') `
    --project-root $ProjectRoot --graph $cameraLookComposePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera base-look compose paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraLookCompose,$cameraLookComposePaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera base-look compose link integrity failed with exit code $LASTEXITCODE." }
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_base_look_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera base-look live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraLookLiveContracts = @(
    @('reset-camera-look-composition-v1.eddgraph', 'Test-CameraBaseLookResetContracts.py', $cameraLookReset),
    @('validate-camera-look-inputs-v1.eddgraph', 'Test-CameraBaseLookValidationContracts.py', $cameraLookValidation),
    @('build-camera-look-base-values-v1.eddgraph', 'Test-CameraBaseLookBaseValuesContracts.py', $cameraLookBase),
    @('apply-camera-look-authored-overrides-v1.eddgraph', 'Test-CameraBaseLookOverridesContracts.py', $cameraLookOverrides),
    @('commit-camera-look-composition-v1.eddgraph', 'Test-CameraBaseLookCommitContracts.py', $cameraLookCommit),
    @('compose-camera-look-v1.eddgraph', 'Test-CameraBaseLookComposeContracts.py', $cameraLookCompose)
)
foreach ($liveContract in $cameraLookLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera base-look link integrity failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphTopologyMatch.py') `
        --project-root $ProjectRoot --expected $liveContract[2] --actual $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera base-look topology changed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera base-look graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
$cameraComfortRoot = Join-Path $scratchRoot ("edd-camera-comfort-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraComfortRoot -Force | Out-Null
$cameraComfortReset = Join-Path $cameraComfortRoot 'reset-camera-viewer-comfort-v1.eddgraph'
$cameraComfortResetPaste = Join-Path $cameraComfortRoot 'reset-camera-viewer-comfort-v1-paste.eddgraph'
$cameraComfortResetRepeat = Join-Path $cameraComfortRoot 'reset-camera-viewer-comfort-v1-repeat.eddgraph'
$cameraComfortResetRepeatPaste = Join-Path $cameraComfortRoot 'reset-camera-viewer-comfort-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortReset,$cameraComfortResetPaste),@($cameraComfortResetRepeat,$cameraComfortResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortReset,$cameraComfortResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-viewer-comfort-v1.eddgraph')),
    @($cameraComfortResetPaste,$cameraComfortResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-viewer-comfort-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort reset generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortReset
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort reset paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortReset,$cameraComfortResetPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort reset link integrity failed with exit code $LASTEXITCODE." }
}
$cameraComfortValidation = Join-Path $cameraComfortRoot 'validate-camera-viewer-comfort-inputs-v1.eddgraph'
$cameraComfortValidationPaste = Join-Path $cameraComfortRoot 'validate-camera-viewer-comfort-inputs-v1-paste.eddgraph'
$cameraComfortValidationRepeat = Join-Path $cameraComfortRoot 'validate-camera-viewer-comfort-inputs-v1-repeat.eddgraph'
$cameraComfortValidationRepeatPaste = Join-Path $cameraComfortRoot 'validate-camera-viewer-comfort-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortValidation,$cameraComfortValidationPaste),@($cameraComfortValidationRepeat,$cameraComfortValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortValidation,$cameraComfortValidationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-viewer-comfort-inputs-v1.eddgraph')),
    @($cameraComfortValidationPaste,$cameraComfortValidationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-viewer-comfort-inputs-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort validation generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortValidation
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort validation paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortValidation,$cameraComfortValidationPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort validation link integrity failed with exit code $LASTEXITCODE." }
}
$cameraComfortMotion = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-motion-v1.eddgraph'
$cameraComfortMotionPaste = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-motion-v1-paste.eddgraph'
$cameraComfortMotionRepeat = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-motion-v1-repeat.eddgraph'
$cameraComfortMotionRepeatPaste = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-motion-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortMotion,$cameraComfortMotionPaste),@($cameraComfortMotionRepeat,$cameraComfortMotionRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortMotionGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort motion generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortMotion,$cameraComfortMotionRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-viewer-comfort-motion-v1.eddgraph')),
    @($cameraComfortMotionPaste,$cameraComfortMotionRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-viewer-comfort-motion-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort motion generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortMotion
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortMotionContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortMotion
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort motion full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortMotionContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortMotionPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort motion paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortMotion,$cameraComfortMotionPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort motion link integrity failed with exit code $LASTEXITCODE." }
}
$cameraComfortChannels = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-channels-v1.eddgraph'
$cameraComfortChannelsPaste = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-channels-v1-paste.eddgraph'
$cameraComfortChannelsRepeat = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-channels-v1-repeat.eddgraph'
$cameraComfortChannelsRepeatPaste = Join-Path $cameraComfortRoot 'build-camera-viewer-comfort-channels-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortChannels,$cameraComfortChannelsPaste),@($cameraComfortChannelsRepeat,$cameraComfortChannelsRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortChannelsGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort channels generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortChannels,$cameraComfortChannelsRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-viewer-comfort-channels-v1.eddgraph')),
    @($cameraComfortChannelsPaste,$cameraComfortChannelsRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-viewer-comfort-channels-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort channels generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortChannels
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortChannelsContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortChannels
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort channels full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortChannelsContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortChannelsPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort channels paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortChannels,$cameraComfortChannelsPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort channels link integrity failed with exit code $LASTEXITCODE." }
}
$cameraComfortCommit = Join-Path $cameraComfortRoot 'commit-camera-viewer-comfort-v1.eddgraph'
$cameraComfortCommitPaste = Join-Path $cameraComfortRoot 'commit-camera-viewer-comfort-v1-paste.eddgraph'
$cameraComfortCommitRepeat = Join-Path $cameraComfortRoot 'commit-camera-viewer-comfort-v1-repeat.eddgraph'
$cameraComfortCommitRepeatPaste = Join-Path $cameraComfortRoot 'commit-camera-viewer-comfort-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortCommit,$cameraComfortCommitPaste),@($cameraComfortCommitRepeat,$cameraComfortCommitRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortCommitGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort commit generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortCommit,$cameraComfortCommitRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-viewer-comfort-v1.eddgraph')),
    @($cameraComfortCommitPaste,$cameraComfortCommitRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-viewer-comfort-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort commit generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortCommit
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortCommit
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort commit paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortCommit,$cameraComfortCommitPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort commit link integrity failed with exit code $LASTEXITCODE." }
}
$cameraComfortApply = Join-Path $cameraComfortRoot 'apply-camera-viewer-comfort-v1.eddgraph'
$cameraComfortApplyPaste = Join-Path $cameraComfortRoot 'apply-camera-viewer-comfort-v1-paste.eddgraph'
$cameraComfortApplyRepeat = Join-Path $cameraComfortRoot 'apply-camera-viewer-comfort-v1-repeat.eddgraph'
$cameraComfortApplyRepeatPaste = Join-Path $cameraComfortRoot 'apply-camera-viewer-comfort-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraComfortApply,$cameraComfortApplyPaste),@($cameraComfortApplyRepeat,$cameraComfortApplyRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraViewerComfortApplyGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort apply generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraComfortApply,$cameraComfortApplyRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-camera-viewer-comfort-v1.eddgraph')),
    @($cameraComfortApplyPaste,$cameraComfortApplyRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-camera-viewer-comfort-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera viewer-comfort apply generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraComfortApply
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortApplyContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortApply
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort apply full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraViewerComfortApplyContracts.py') `
    --project-root $ProjectRoot --graph $cameraComfortApplyPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort apply paste contracts failed with exit code $LASTEXITCODE." }
foreach ($graph in @($cameraComfortApply,$cameraComfortApplyPaste)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $graph
    if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort apply link integrity failed with exit code $LASTEXITCODE." }
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_viewer_comfort_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera viewer-comfort live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraComfortLiveContracts = @(
    @('reset-camera-viewer-comfort-v1.eddgraph', 'Test-CameraViewerComfortResetContracts.py', $cameraComfortReset),
    @('validate-camera-viewer-comfort-inputs-v1.eddgraph', 'Test-CameraViewerComfortValidationContracts.py', $cameraComfortValidation),
    @('build-camera-viewer-comfort-motion-v1.eddgraph', 'Test-CameraViewerComfortMotionContracts.py', $cameraComfortMotion),
    @('build-camera-viewer-comfort-channels-v1.eddgraph', 'Test-CameraViewerComfortChannelsContracts.py', $cameraComfortChannels),
    @('commit-camera-viewer-comfort-v1.eddgraph', 'Test-CameraViewerComfortCommitContracts.py', $cameraComfortCommit),
    @('apply-camera-viewer-comfort-v1.eddgraph', 'Test-CameraViewerComfortApplyContracts.py', $cameraComfortApply)
)
foreach ($liveContract in $cameraComfortLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera viewer-comfort link integrity failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphTopologyMatch.py') `
        --project-root $ProjectRoot --expected $liveContract[2] --actual $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera viewer-comfort topology changed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera viewer-comfort graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
$cameraDofRoot = Join-Path $scratchRoot ("edd-camera-dof-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraDofRoot -Force | Out-Null
$cameraDofReset = Join-Path $cameraDofRoot 'reset-camera-dof-diagnostics-v1.eddgraph'
$cameraDofResetPaste = Join-Path $cameraDofRoot 'reset-camera-dof-diagnostics-v1-paste.eddgraph'
$cameraDofResetRepeat = Join-Path $cameraDofRoot 'reset-camera-dof-diagnostics-v1-repeat.eddgraph'
$cameraDofResetRepeatPaste = Join-Path $cameraDofRoot 'reset-camera-dof-diagnostics-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDofReset,$cameraDofResetPaste),@($cameraDofResetRepeat,$cameraDofResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDofDiagnosticsResetGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera DOF reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDofReset,$cameraDofResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-dof-diagnostics-v1.eddgraph')),
    @($cameraDofResetPaste,$cameraDofResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-dof-diagnostics-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera DOF reset generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDofReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsResetContracts.py') --project-root $ProjectRoot --graph $cameraDofReset
if ($LASTEXITCODE -ne 0) { throw "Camera DOF reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsResetContracts.py') --project-root $ProjectRoot --graph $cameraDofResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera DOF reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraDofStage = Join-Path $cameraDofRoot 'stage-evaluated-camera-dof-frame-v1.eddgraph'
$cameraDofStagePaste = Join-Path $cameraDofRoot 'stage-evaluated-camera-dof-frame-v1-paste.eddgraph'
$cameraDofStageRepeat = Join-Path $cameraDofRoot 'stage-evaluated-camera-dof-frame-v1-repeat.eddgraph'
$cameraDofStageRepeatPaste = Join-Path $cameraDofRoot 'stage-evaluated-camera-dof-frame-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDofStage,$cameraDofStagePaste),@($cameraDofStageRepeat,$cameraDofStageRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDofDiagnosticsStageGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera DOF stage generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDofStage,$cameraDofStageRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-evaluated-camera-dof-frame-v1.eddgraph')),
    @($cameraDofStagePaste,$cameraDofStageRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-evaluated-camera-dof-frame-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera DOF stage generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDofStage
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsStageContracts.py') --project-root $ProjectRoot --graph $cameraDofStage
if ($LASTEXITCODE -ne 0) { throw "Camera DOF stage full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsStageContracts.py') --project-root $ProjectRoot --graph $cameraDofStagePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera DOF stage paste contracts failed with exit code $LASTEXITCODE." }
$cameraDofCompute = Join-Path $cameraDofRoot 'compute-camera-dof-diagnostics-v1.eddgraph'
$cameraDofComputePaste = Join-Path $cameraDofRoot 'compute-camera-dof-diagnostics-v1-paste.eddgraph'
$cameraDofComputeRepeat = Join-Path $cameraDofRoot 'compute-camera-dof-diagnostics-v1-repeat.eddgraph'
$cameraDofComputeRepeatPaste = Join-Path $cameraDofRoot 'compute-camera-dof-diagnostics-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDofCompute,$cameraDofComputePaste),@($cameraDofComputeRepeat,$cameraDofComputeRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDofDiagnosticsComputeGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera DOF compute generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDofCompute,$cameraDofComputeRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compute-camera-dof-diagnostics-v1.eddgraph')),
    @($cameraDofComputePaste,$cameraDofComputeRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compute-camera-dof-diagnostics-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera DOF compute generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDofCompute
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsComputeContracts.py') --project-root $ProjectRoot --graph $cameraDofCompute
if ($LASTEXITCODE -ne 0) { throw "Camera DOF compute full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsComputeContracts.py') --project-root $ProjectRoot --graph $cameraDofComputePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera DOF compute paste contracts failed with exit code $LASTEXITCODE." }
$cameraDofEvaluate = Join-Path $cameraDofRoot 'evaluate-camera-dof-diagnostics-v1.eddgraph'
$cameraDofEvaluatePaste = Join-Path $cameraDofRoot 'evaluate-camera-dof-diagnostics-v1-paste.eddgraph'
$cameraDofEvaluateRepeat = Join-Path $cameraDofRoot 'evaluate-camera-dof-diagnostics-v1-repeat.eddgraph'
$cameraDofEvaluateRepeatPaste = Join-Path $cameraDofRoot 'evaluate-camera-dof-diagnostics-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraDofEvaluate,$cameraDofEvaluatePaste),@($cameraDofEvaluateRepeat,$cameraDofEvaluateRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraDofDiagnosticsEvaluateGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera DOF evaluate generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraDofEvaluate,$cameraDofEvaluateRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-camera-dof-diagnostics-v1.eddgraph')),
    @($cameraDofEvaluatePaste,$cameraDofEvaluateRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-camera-dof-diagnostics-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera DOF evaluate generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraDofEvaluate
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsEvaluateContracts.py') --project-root $ProjectRoot --graph $cameraDofEvaluate
if ($LASTEXITCODE -ne 0) { throw "Camera DOF evaluate full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraDofDiagnosticsEvaluateContracts.py') --project-root $ProjectRoot --graph $cameraDofEvaluatePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera DOF evaluate paste contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_dof_diagnostics_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera DOF live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraDofLiveContracts = @(
    @('reset-camera-dof-diagnostics-v1.eddgraph', 'Test-CameraDofDiagnosticsResetContracts.py'),
    @('stage-evaluated-camera-dof-frame-v1.eddgraph', 'Test-CameraDofDiagnosticsStageContracts.py'),
    @('compute-camera-dof-diagnostics-v1.eddgraph', 'Test-CameraDofDiagnosticsComputeContracts.py'),
    @('evaluate-camera-dof-diagnostics-v1.eddgraph', 'Test-CameraDofDiagnosticsEvaluateContracts.py')
)
foreach ($liveContract in $cameraDofLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera DOF graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
$cameraFocusRoot = Join-Path $scratchRoot ("edd-camera-focus-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $cameraFocusRoot -Force | Out-Null
$cameraFocusReset = Join-Path $cameraFocusRoot 'reset-camera-focus-compile-v1.eddgraph'
$cameraFocusResetPaste = Join-Path $cameraFocusRoot 'reset-camera-focus-compile-v1-paste.eddgraph'
$cameraFocusResetRepeat = Join-Path $cameraFocusRoot 'reset-camera-focus-compile-v1-repeat.eddgraph'
$cameraFocusResetRepeatPaste = Join-Path $cameraFocusRoot 'reset-camera-focus-compile-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusReset,$cameraFocusResetPaste),@($cameraFocusResetRepeat,$cameraFocusResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusCompileResetGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusReset,$cameraFocusResetRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-focus-compile-v1.eddgraph')),
    @($cameraFocusResetPaste,$cameraFocusResetRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-focus-compile-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus reset generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCompileResetContracts.py') --project-root $ProjectRoot --graph $cameraFocusReset
if ($LASTEXITCODE -ne 0) { throw "Camera focus reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCompileResetContracts.py') --project-root $ProjectRoot --graph $cameraFocusResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraFocusSetHere = Join-Path $cameraFocusRoot 'set-camera-focus-here-v1.eddgraph'
$cameraFocusSetHerePaste = Join-Path $cameraFocusRoot 'set-camera-focus-here-v1-paste.eddgraph'
$cameraFocusSetHereRepeat = Join-Path $cameraFocusRoot 'set-camera-focus-here-v1-repeat.eddgraph'
$cameraFocusSetHereRepeatPaste = Join-Path $cameraFocusRoot 'set-camera-focus-here-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusSetHere,$cameraFocusSetHerePaste),@($cameraFocusSetHereRepeat,$cameraFocusSetHereRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusSetHereGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus Set Here generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusSetHere,$cameraFocusSetHereRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\set-camera-focus-here-v1.eddgraph')),
    @($cameraFocusSetHerePaste,$cameraFocusSetHereRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\set-camera-focus-here-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus Set Here generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusSetHere
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusSetHereContracts.py') --project-root $ProjectRoot --graph $cameraFocusSetHere
if ($LASTEXITCODE -ne 0) { throw "Camera focus Set Here full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusSetHereContracts.py') --project-root $ProjectRoot --graph $cameraFocusSetHerePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus Set Here paste contracts failed with exit code $LASTEXITCODE." }
$cameraFocusValidation = Join-Path $cameraFocusRoot 'validate-camera-focus-inputs-v1.eddgraph'
$cameraFocusValidationPaste = Join-Path $cameraFocusRoot 'validate-camera-focus-inputs-v1-paste.eddgraph'
$cameraFocusValidationRepeat = Join-Path $cameraFocusRoot 'validate-camera-focus-inputs-v1-repeat.eddgraph'
$cameraFocusValidationRepeatPaste = Join-Path $cameraFocusRoot 'validate-camera-focus-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusValidation,$cameraFocusValidationPaste),@($cameraFocusValidationRepeat,$cameraFocusValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusValidationGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusValidation,$cameraFocusValidationRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-focus-inputs-v1.eddgraph')),
    @($cameraFocusValidationPaste,$cameraFocusValidationRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-focus-inputs-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus validation generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusValidationContracts.py') --project-root $ProjectRoot --graph $cameraFocusValidation
if ($LASTEXITCODE -ne 0) { throw "Camera focus validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusValidationContracts.py') --project-root $ProjectRoot --graph $cameraFocusValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus validation paste contracts failed with exit code $LASTEXITCODE." }
$cameraFocusCandidates = Join-Path $cameraFocusRoot 'build-camera-focus-distance-candidates-v1.eddgraph'
$cameraFocusCandidatesPaste = Join-Path $cameraFocusRoot 'build-camera-focus-distance-candidates-v1-paste.eddgraph'
$cameraFocusCandidatesRepeat = Join-Path $cameraFocusRoot 'build-camera-focus-distance-candidates-v1-repeat.eddgraph'
$cameraFocusCandidatesRepeatPaste = Join-Path $cameraFocusRoot 'build-camera-focus-distance-candidates-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusCandidates,$cameraFocusCandidatesPaste),@($cameraFocusCandidatesRepeat,$cameraFocusCandidatesRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusCandidatesGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus candidate generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusCandidates,$cameraFocusCandidatesRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-focus-distance-candidates-v1.eddgraph')),
    @($cameraFocusCandidatesPaste,$cameraFocusCandidatesRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-focus-distance-candidates-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus candidate generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusCandidates
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraFocusCandidates
if ($LASTEXITCODE -ne 0) { throw "Camera focus candidate full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraFocusCandidatesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus candidate paste contracts failed with exit code $LASTEXITCODE." }
$cameraFocusCommit = Join-Path $cameraFocusRoot 'commit-camera-focus-distance-channel-v1.eddgraph'
$cameraFocusCommitPaste = Join-Path $cameraFocusRoot 'commit-camera-focus-distance-channel-v1-paste.eddgraph'
$cameraFocusCommitRepeat = Join-Path $cameraFocusRoot 'commit-camera-focus-distance-channel-v1-repeat.eddgraph'
$cameraFocusCommitRepeatPaste = Join-Path $cameraFocusRoot 'commit-camera-focus-distance-channel-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusCommit,$cameraFocusCommitPaste),@($cameraFocusCommitRepeat,$cameraFocusCommitRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusCommitGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus commit generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusCommit,$cameraFocusCommitRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-focus-distance-channel-v1.eddgraph')),
    @($cameraFocusCommitPaste,$cameraFocusCommitRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-focus-distance-channel-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus commit generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusCommit
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCommitContracts.py') --project-root $ProjectRoot --graph $cameraFocusCommit
if ($LASTEXITCODE -ne 0) { throw "Camera focus commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCommitContracts.py') --project-root $ProjectRoot --graph $cameraFocusCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus commit paste contracts failed with exit code $LASTEXITCODE." }
$cameraFocusCompile = Join-Path $cameraFocusRoot 'compile-camera-focus-distance-channel-v1.eddgraph'
$cameraFocusCompilePaste = Join-Path $cameraFocusRoot 'compile-camera-focus-distance-channel-v1-paste.eddgraph'
$cameraFocusCompileRepeat = Join-Path $cameraFocusRoot 'compile-camera-focus-distance-channel-v1-repeat.eddgraph'
$cameraFocusCompileRepeatPaste = Join-Path $cameraFocusRoot 'compile-camera-focus-distance-channel-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraFocusCompile,$cameraFocusCompilePaste),@($cameraFocusCompileRepeat,$cameraFocusCompileRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraFocusCompileGraph.py') --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera focus compile generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraFocusCompile,$cameraFocusCompileRepeat,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-focus-distance-channel-v1.eddgraph')),
    @($cameraFocusCompilePaste,$cameraFocusCompileRepeatPaste,(Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-focus-distance-channel-v1-paste.eddgraph'))
)) {
    $hashes=@((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[1]).Hash,(Get-FileHash -Algorithm SHA256 $comparison[2]).Hash)
    if (@($hashes|Select-Object -Unique).Count -ne 1) { throw "Camera focus compile generation or checked-in snippet drifted." }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraFocusCompile
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCompileContracts.py') --project-root $ProjectRoot --graph $cameraFocusCompile
if ($LASTEXITCODE -ne 0) { throw "Camera focus compile full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraFocusCompileContracts.py') --project-root $ProjectRoot --graph $cameraFocusCompilePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera focus compile paste contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_focus_helper_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera focus live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraFocusLiveContracts = @(
    @('reset-camera-focus-compile-v1.eddgraph', 'Test-CameraFocusCompileResetContracts.py'),
    @('set-camera-focus-here-v1.eddgraph', 'Test-CameraFocusSetHereContracts.py'),
    @('validate-camera-focus-inputs-v1.eddgraph', 'Test-CameraFocusValidationContracts.py'),
    @('build-camera-focus-distance-candidates-v1.eddgraph', 'Test-CameraFocusCandidatesContracts.py'),
    @('commit-camera-focus-distance-channel-v1.eddgraph', 'Test-CameraFocusCommitContracts.py'),
    @('compile-camera-focus-distance-channel-v1.eddgraph', 'Test-CameraFocusCompileContracts.py')
)
foreach ($liveContract in $cameraFocusLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera focus graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_engine_application_validators.py')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine live-validator contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineNativeNodeForms.py') `
    --project-root $ProjectRoot `
    --basic (Join-Path $ProjectRoot 'tools\blueprint\templates\camera-engine-basic-node-forms.eddgraph') `
    --structs (Join-Path $ProjectRoot 'tools\blueprint\templates\camera-engine-struct-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine native node-form contracts failed with exit code $LASTEXITCODE."
}
$cameraApplyResetNonce = [guid]::NewGuid().ToString('N')
$cameraApplyResetRoot = Join-Path $scratchRoot "edd-camera-apply-reset-$cameraApplyResetNonce"
New-Item -ItemType Directory -Path $cameraApplyResetRoot -Force | Out-Null
$cameraApplyReset = Join-Path $cameraApplyResetRoot 'reset-camera-engine-application-result-v1.eddgraph'
$cameraApplyResetPaste = Join-Path $cameraApplyResetRoot 'reset-camera-engine-application-result-v1-paste.eddgraph'
$cameraApplyResetRepeat = Join-Path $cameraApplyResetRoot 'reset-camera-engine-application-result-v1-repeat.eddgraph'
$cameraApplyResetRepeatPaste = Join-Path $cameraApplyResetRoot 'reset-camera-engine-application-result-v1-repeat-paste.eddgraph'
foreach ($pair in @(
    @($cameraApplyReset, $cameraApplyResetPaste),
    @($cameraApplyResetRepeat, $cameraApplyResetRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraEngineApplicationResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) {
        throw "Camera engine-application reset generation failed with exit code $LASTEXITCODE."
    }
}
foreach ($comparison in @(
    @($cameraApplyReset, $cameraApplyResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-engine-application-result-v1.eddgraph')),
    @($cameraApplyResetPaste, $cameraApplyResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-engine-application-result-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[1]).Hash) {
        throw "Camera engine-application reset generation is not deterministic: $($comparison[0])"
    }
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[2]).Hash) {
        throw "Checked-in camera engine-application reset snippet drifted: $($comparison[2])"
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraApplyReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyReset
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application reset full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyResetPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application reset paste contracts failed with exit code $LASTEXITCODE."
}
$cameraApplyStage = Join-Path $cameraApplyResetRoot 'stage-evaluated-camera-channel-frame-v1.eddgraph'
$cameraApplyStagePaste = Join-Path $cameraApplyResetRoot 'stage-evaluated-camera-channel-frame-v1-paste.eddgraph'
$cameraApplyStageRepeat = Join-Path $cameraApplyResetRoot 'stage-evaluated-camera-channel-frame-v1-repeat.eddgraph'
$cameraApplyStageRepeatPaste = Join-Path $cameraApplyResetRoot 'stage-evaluated-camera-channel-frame-v1-repeat-paste.eddgraph'
foreach ($pair in @(
    @($cameraApplyStage, $cameraApplyStagePaste),
    @($cameraApplyStageRepeat, $cameraApplyStageRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraEngineApplicationStageGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) {
        throw "Camera engine-application staging generation failed with exit code $LASTEXITCODE."
    }
}
foreach ($comparison in @(
    @($cameraApplyStage, $cameraApplyStageRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-evaluated-camera-channel-frame-v1.eddgraph')),
    @($cameraApplyStagePaste, $cameraApplyStageRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-evaluated-camera-channel-frame-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[1]).Hash) {
        throw "Camera engine-application staging generation is not deterministic: $($comparison[0])"
    }
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[2]).Hash) {
        throw "Checked-in camera engine-application staging snippet drifted: $($comparison[2])"
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraApplyStage
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationStageContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyStage
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application staging full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationStageContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyStagePaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application staging paste contracts failed with exit code $LASTEXITCODE."
}
$cameraApplyValidation = Join-Path $cameraApplyResetRoot 'validate-camera-engine-application-inputs-v1.eddgraph'
$cameraApplyValidationPaste = Join-Path $cameraApplyResetRoot 'validate-camera-engine-application-inputs-v1-paste.eddgraph'
$cameraApplyValidationRepeat = Join-Path $cameraApplyResetRoot 'validate-camera-engine-application-inputs-v1-repeat.eddgraph'
$cameraApplyValidationRepeatPaste = Join-Path $cameraApplyResetRoot 'validate-camera-engine-application-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(
    @($cameraApplyValidation, $cameraApplyValidationPaste),
    @($cameraApplyValidationRepeat, $cameraApplyValidationRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraEngineApplicationValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) {
        throw "Camera engine-application validation generation failed with exit code $LASTEXITCODE."
    }
}
foreach ($comparison in @(
    @($cameraApplyValidation, $cameraApplyValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-engine-application-inputs-v1.eddgraph')),
    @($cameraApplyValidationPaste, $cameraApplyValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-engine-application-inputs-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[1]).Hash) {
        throw "Camera engine-application validation generation is not deterministic: $($comparison[0])"
    }
    if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[2]).Hash) {
        throw "Checked-in camera engine-application validation snippet drifted: $($comparison[2])"
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraApplyValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyValidation
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application validation full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraEngineApplicationValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraApplyValidationPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Camera engine-application validation paste contracts failed with exit code $LASTEXITCODE."
}
$cameraNativeSpecs = @(
    @{ Label = 'capture'; Build = 'Build-CameraEngineStateCaptureGraph.py'; Test = 'Test-CameraEngineStateCaptureContracts.py'; Stem = 'capture-camera-engine-state-v1' },
    @{ Label = 'apply'; Build = 'Build-CameraEngineFrameApplyGraph.py'; Test = 'Test-CameraEngineFrameApplyContracts.py'; Stem = 'apply-camera-engine-frame-v1' },
    @{ Label = 'restore'; Build = 'Build-CameraEngineStateRestoreGraph.py'; Test = 'Test-CameraEngineStateRestoreContracts.py'; Stem = 'restore-camera-engine-state-v1' },
    @{ Label = 'orchestrator'; Build = 'Build-CameraEngineApplicationGraph.py'; Test = 'Test-CameraEngineApplicationContracts.py'; Stem = 'apply-evaluated-camera-channel-frame-v1' }
)
foreach ($spec in $cameraNativeSpecs) {
    $generated = Join-Path $cameraApplyResetRoot "$($spec.Stem).eddgraph"
    $generatedPaste = Join-Path $cameraApplyResetRoot "$($spec.Stem)-paste.eddgraph"
    $repeat = Join-Path $cameraApplyResetRoot "$($spec.Stem)-repeat.eddgraph"
    $repeatPaste = Join-Path $cameraApplyResetRoot "$($spec.Stem)-repeat-paste.eddgraph"
    foreach ($pair in @(@($generated, $generatedPaste), @($repeat, $repeatPaste))) {
        & python (Join-Path $ProjectRoot "tools\blueprint\$($spec.Build)") `
            --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
        if ($LASTEXITCODE -ne 0) {
            throw "Camera engine $($spec.Label) generation failed with exit code $LASTEXITCODE."
        }
    }
    foreach ($comparison in @(
        @($generated, $repeat, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($spec.Stem).eddgraph")),
        @($generatedPaste, $repeatPaste, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($spec.Stem)-paste.eddgraph"))
    )) {
        if ((Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[1]).Hash -or
            (Get-FileHash -Algorithm SHA256 $comparison[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison[2]).Hash) {
            throw "Camera engine $($spec.Label) generation is not byte deterministic."
        }
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $generated
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec.Test)") --project-root $ProjectRoot --graph $generated
    if ($LASTEXITCODE -ne 0) { throw "Camera engine $($spec.Label) full contracts failed with exit code $LASTEXITCODE." }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec.Test)") --project-root $ProjectRoot --graph $generatedPaste --paste
    if ($LASTEXITCODE -ne 0) { throw "Camera engine $($spec.Label) paste contracts failed with exit code $LASTEXITCODE." }
}
$cameraEngineLiveSpecs = @(
    @{ Label = 'reset'; Test = 'Test-CameraEngineApplicationResetContracts.py'; File = 'reset-camera-engine-application-result-v1.eddgraph' },
    @{ Label = 'stage'; Test = 'Test-CameraEngineApplicationStageContracts.py'; File = 'stage-evaluated-camera-channel-frame-v1.eddgraph' },
    @{ Label = 'validation'; Test = 'Test-CameraEngineApplicationValidationContracts.py'; File = 'validate-camera-engine-application-inputs-v1.eddgraph' },
    @{ Label = 'capture'; Test = 'Test-CameraEngineStateCaptureContracts.py'; File = 'capture-camera-engine-state-v1.eddgraph' },
    @{ Label = 'apply'; Test = 'Test-CameraEngineFrameApplyContracts.py'; File = 'apply-camera-engine-frame-v1.eddgraph' },
    @{ Label = 'restore'; Test = 'Test-CameraEngineStateRestoreContracts.py'; File = 'restore-camera-engine-state-v1.eddgraph' },
    @{ Label = 'orchestrator'; Test = 'Test-CameraEngineApplicationContracts.py'; File = 'apply-evaluated-camera-channel-frame-v1.eddgraph' }
)
foreach ($spec in $cameraEngineLiveSpecs) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($spec.File)"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec.Test)") --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) { throw "Live camera engine $($spec.Label) contracts failed with exit code $LASTEXITCODE." }
}
$cameraScalarNonce = [guid]::NewGuid().ToString('N')
$cameraScalarRoot = Join-Path $scratchRoot "edd-camera-scalar-$cameraScalarNonce"
New-Item -ItemType Directory -Path $cameraScalarRoot -Force | Out-Null
$cameraScalarReset = Join-Path $cameraScalarRoot 'reset-camera-scalar-track-compile-v1.eddgraph'
$cameraScalarResetPaste = Join-Path $cameraScalarRoot 'reset-camera-scalar-track-compile-v1-paste.eddgraph'
$cameraScalarResetRepeat = Join-Path $cameraScalarRoot 'reset-camera-scalar-track-compile-v1-repeat.eddgraph'
$cameraScalarResetRepeatPaste = Join-Path $cameraScalarRoot 'reset-camera-scalar-track-compile-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraScalarReset, $cameraScalarResetPaste), @($cameraScalarResetRepeat, $cameraScalarResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraScalarTrackResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera scalar reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraScalarReset, $cameraScalarResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-scalar-track-compile-v1.eddgraph')),
    @($cameraScalarResetPaste, $cameraScalarResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-scalar-track-compile-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera scalar reset generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraScalarReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackResetContracts.py') --project-root $ProjectRoot --graph $cameraScalarReset
if ($LASTEXITCODE -ne 0) { throw "Camera scalar reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackResetContracts.py') --project-root $ProjectRoot --graph $cameraScalarResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera scalar reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraScalarValidation = Join-Path $cameraScalarRoot 'validate-camera-scalar-track-inputs-v1.eddgraph'
$cameraScalarValidationPaste = Join-Path $cameraScalarRoot 'validate-camera-scalar-track-inputs-v1-paste.eddgraph'
$cameraScalarValidationRepeat = Join-Path $cameraScalarRoot 'validate-camera-scalar-track-inputs-v1-repeat.eddgraph'
$cameraScalarValidationRepeatPaste = Join-Path $cameraScalarRoot 'validate-camera-scalar-track-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraScalarValidation, $cameraScalarValidationPaste), @($cameraScalarValidationRepeat, $cameraScalarValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraScalarTrackValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera scalar validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraScalarValidation, $cameraScalarValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-scalar-track-inputs-v1.eddgraph')),
    @($cameraScalarValidationPaste, $cameraScalarValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-scalar-track-inputs-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
            throw 'Camera scalar validation generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraScalarValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackValidationContracts.py') --project-root $ProjectRoot --graph $cameraScalarValidation
if ($LASTEXITCODE -ne 0) { throw "Camera scalar validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackValidationContracts.py') --project-root $ProjectRoot --graph $cameraScalarValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera scalar validation paste contracts failed with exit code $LASTEXITCODE." }
$cameraScalarCandidates = Join-Path $cameraScalarRoot 'build-camera-scalar-track-candidates-v1.eddgraph'
$cameraScalarCandidatesPaste = Join-Path $cameraScalarRoot 'build-camera-scalar-track-candidates-v1-paste.eddgraph'
$cameraScalarCandidatesRepeat = Join-Path $cameraScalarRoot 'build-camera-scalar-track-candidates-v1-repeat.eddgraph'
$cameraScalarCandidatesRepeatPaste = Join-Path $cameraScalarRoot 'build-camera-scalar-track-candidates-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraScalarCandidates, $cameraScalarCandidatesPaste), @($cameraScalarCandidatesRepeat, $cameraScalarCandidatesRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraScalarTrackCandidatesGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera scalar candidates generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraScalarCandidates, $cameraScalarCandidatesRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-scalar-track-candidates-v1.eddgraph')),
    @($cameraScalarCandidatesPaste, $cameraScalarCandidatesRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-camera-scalar-track-candidates-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
            throw 'Camera scalar candidates generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraScalarCandidates
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraScalarCandidates
if ($LASTEXITCODE -ne 0) { throw "Camera scalar candidates full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraScalarTrackCandidatesContracts.py') --project-root $ProjectRoot --graph $cameraScalarCandidatesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera scalar candidates paste contracts failed with exit code $LASTEXITCODE." }
$cameraScalarPublicationStages = @(
    @('commit-camera-scalar-track-v1', 'Build-CameraScalarTrackCommitGraph.py', 'Test-CameraScalarTrackCommitContracts.py'),
    @('compile-camera-scalar-track-v1', 'Build-CameraScalarTrackCompileGraph.py', 'Test-CameraScalarTrackCompileContracts.py'),
    @('reset-camera-scalar-track-result-v1', 'Build-CameraScalarTrackResultResetGraph.py', 'Test-CameraScalarTrackResultResetContracts.py'),
    @('publish-camera-scalar-track-sample-v1', 'Build-CameraScalarTrackPublishGraph.py', 'Test-CameraScalarTrackPublishContracts.py'),
    @('evaluate-camera-scalar-track-segment-v1', 'Build-CameraScalarTrackSegmentGraph.py', 'Test-CameraScalarTrackSegmentContracts.py'),
    @('evaluate-camera-scalar-track-v1', 'Build-CameraScalarTrackEvaluateGraph.py', 'Test-CameraScalarTrackEvaluateContracts.py')
)
foreach ($stage in $cameraScalarPublicationStages) {
    $generated = Join-Path $cameraScalarRoot "$($stage[0]).eddgraph"
    $generatedPaste = Join-Path $cameraScalarRoot "$($stage[0])-paste.eddgraph"
    $repeated = Join-Path $cameraScalarRoot "$($stage[0])-repeat.eddgraph"
    $repeatedPaste = Join-Path $cameraScalarRoot "$($stage[0])-repeat-paste.eddgraph"
    foreach ($pair in @(@($generated, $generatedPaste), @($repeated, $repeatedPaste))) {
        & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[1])") --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
        if ($LASTEXITCODE -ne 0) { throw "Camera scalar $($stage[0]) generation failed with exit code $LASTEXITCODE." }
    }
    foreach ($comparison in @(
        @($generated, $repeated, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($stage[0]).eddgraph")),
        @($generatedPaste, $repeatedPaste, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($stage[0])-paste.eddgraph"))
    )) {
        if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
            (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
                throw "Camera scalar $($stage[0]) generation is not byte deterministic."
        }
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $generated
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[2])") --project-root $ProjectRoot --graph $generated
    if ($LASTEXITCODE -ne 0) { throw "Camera scalar $($stage[0]) full contracts failed with exit code $LASTEXITCODE." }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[2])") --project-root $ProjectRoot --graph $generatedPaste --paste
    if ($LASTEXITCODE -ne 0) { throw "Camera scalar $($stage[0]) paste contracts failed with exit code $LASTEXITCODE." }
}
$cameraScalarLiveStages = @(
    @('reset-camera-scalar-track-compile-v1', 'Test-CameraScalarTrackResetContracts.py'),
    @('validate-camera-scalar-track-inputs-v1', 'Test-CameraScalarTrackValidationContracts.py'),
    @('build-camera-scalar-track-candidates-v1', 'Test-CameraScalarTrackCandidatesContracts.py')
) + @($cameraScalarPublicationStages | ForEach-Object { , @($_[0], $_[2]) })
foreach ($stage in $cameraScalarLiveStages) {
    $live = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($stage[0]).eddgraph"
    $canonical = Join-Path $ProjectRoot "tools\blueprint\snippets\$($stage[0]).eddgraph"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $live
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphLinkIntegrity.py') `
        --project-root $ProjectRoot --graph $live
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera scalar $($stage[0]) link integrity failed with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphTopologyMatch.py') `
        --project-root $ProjectRoot --expected $canonical --actual $live
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera scalar $($stage[0]) topology failed with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[1])") `
        --project-root $ProjectRoot --graph $live
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera scalar $($stage[0]) contracts failed with exit code $LASTEXITCODE."
    }
}
& python (Join-Path $ProjectRoot 'tools\unreal\test_camera_scalar_track_validators.py')
if ($LASTEXITCODE -ne 0) { throw "Camera scalar-track live-tool contracts failed with exit code $LASTEXITCODE." }
$cameraChannelNonce = [guid]::NewGuid().ToString('N')
$cameraChannelRoot = Join-Path $scratchRoot "edd-camera-channel-$cameraChannelNonce"
New-Item -ItemType Directory -Path $cameraChannelRoot -Force | Out-Null
$cameraChannelReset = Join-Path $cameraChannelRoot 'reset-camera-channel-compile-v1.eddgraph'
$cameraChannelResetPaste = Join-Path $cameraChannelRoot 'reset-camera-channel-compile-v1-paste.eddgraph'
$cameraChannelResetRepeat = Join-Path $cameraChannelRoot 'reset-camera-channel-compile-v1-repeat.eddgraph'
$cameraChannelResetRepeatPaste = Join-Path $cameraChannelRoot 'reset-camera-channel-compile-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelReset, $cameraChannelResetPaste), @($cameraChannelResetRepeat, $cameraChannelResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelCompileResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel compile-reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelReset, $cameraChannelResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-channel-compile-v1.eddgraph')),
    @($cameraChannelResetPaste, $cameraChannelResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-channel-compile-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel compile-reset generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCompileResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelReset
if ($LASTEXITCODE -ne 0) { throw "Camera channel compile-reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCompileResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel compile-reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelValidation = Join-Path $cameraChannelRoot 'validate-camera-channel-inputs-v1.eddgraph'
$cameraChannelValidationPaste = Join-Path $cameraChannelRoot 'validate-camera-channel-inputs-v1-paste.eddgraph'
$cameraChannelValidationRepeat = Join-Path $cameraChannelRoot 'validate-camera-channel-inputs-v1-repeat.eddgraph'
$cameraChannelValidationRepeatPaste = Join-Path $cameraChannelRoot 'validate-camera-channel-inputs-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelValidation, $cameraChannelValidationPaste), @($cameraChannelValidationRepeat, $cameraChannelValidationRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelValidationGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel validation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelValidation, $cameraChannelValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-channel-inputs-v1.eddgraph')),
    @($cameraChannelValidationPaste, $cameraChannelValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-camera-channel-inputs-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel validation generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelValidation
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelValidation
if ($LASTEXITCODE -ne 0) { throw "Camera channel validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelValidationContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel validation paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelCandidate = Join-Path $cameraChannelRoot 'compile-camera-channel-candidate-v1.eddgraph'
$cameraChannelCandidatePaste = Join-Path $cameraChannelRoot 'compile-camera-channel-candidate-v1-paste.eddgraph'
$cameraChannelCandidateRepeat = Join-Path $cameraChannelRoot 'compile-camera-channel-candidate-v1-repeat.eddgraph'
$cameraChannelCandidateRepeatPaste = Join-Path $cameraChannelRoot 'compile-camera-channel-candidate-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelCandidate, $cameraChannelCandidatePaste), @($cameraChannelCandidateRepeat, $cameraChannelCandidateRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelCandidateGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel candidate generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelCandidate, $cameraChannelCandidateRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-channel-candidate-v1.eddgraph')),
    @($cameraChannelCandidatePaste, $cameraChannelCandidateRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-channel-candidate-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel candidate generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelCandidate
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCandidateContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCandidate
if ($LASTEXITCODE -ne 0) { throw "Camera channel candidate full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCandidateContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCandidatePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel candidate paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelCommit = Join-Path $cameraChannelRoot 'commit-camera-channel-assembly-v1.eddgraph'
$cameraChannelCommitPaste = Join-Path $cameraChannelRoot 'commit-camera-channel-assembly-v1-paste.eddgraph'
$cameraChannelCommitRepeat = Join-Path $cameraChannelRoot 'commit-camera-channel-assembly-v1-repeat.eddgraph'
$cameraChannelCommitRepeatPaste = Join-Path $cameraChannelRoot 'commit-camera-channel-assembly-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelCommit, $cameraChannelCommitPaste), @($cameraChannelCommitRepeat, $cameraChannelCommitRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelCommitGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel commit generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelCommit, $cameraChannelCommitRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-channel-assembly-v1.eddgraph')),
    @($cameraChannelCommitPaste, $cameraChannelCommitRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-camera-channel-assembly-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel commit generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelCommit
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCommit
if ($LASTEXITCODE -ne 0) { throw "Camera channel commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCommitContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel commit paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelCompile = Join-Path $cameraChannelRoot 'compile-camera-channel-assembly-v1.eddgraph'
$cameraChannelCompilePaste = Join-Path $cameraChannelRoot 'compile-camera-channel-assembly-v1-paste.eddgraph'
$cameraChannelCompileRepeat = Join-Path $cameraChannelRoot 'compile-camera-channel-assembly-v1-repeat.eddgraph'
$cameraChannelCompileRepeatPaste = Join-Path $cameraChannelRoot 'compile-camera-channel-assembly-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelCompile, $cameraChannelCompilePaste), @($cameraChannelCompileRepeat, $cameraChannelCompileRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelCompileGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel compile generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelCompile, $cameraChannelCompileRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-channel-assembly-v1.eddgraph')),
    @($cameraChannelCompilePaste, $cameraChannelCompileRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-camera-channel-assembly-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel compile generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelCompile
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCompileContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCompile
if ($LASTEXITCODE -ne 0) { throw "Camera channel compile full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelCompileContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelCompilePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel compile paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelResultReset = Join-Path $cameraChannelRoot 'reset-camera-channel-result-v1.eddgraph'
$cameraChannelResultResetPaste = Join-Path $cameraChannelRoot 'reset-camera-channel-result-v1-paste.eddgraph'
$cameraChannelResultResetRepeat = Join-Path $cameraChannelRoot 'reset-camera-channel-result-v1-repeat.eddgraph'
$cameraChannelResultResetRepeatPaste = Join-Path $cameraChannelRoot 'reset-camera-channel-result-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelResultReset, $cameraChannelResultResetPaste), @($cameraChannelResultResetRepeat, $cameraChannelResultResetRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelResultResetGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel result-reset generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelResultReset, $cameraChannelResultResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-channel-result-v1.eddgraph')),
    @($cameraChannelResultResetPaste, $cameraChannelResultResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-camera-channel-result-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel result-reset generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelResultReset
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelResultResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelResultReset
if ($LASTEXITCODE -ne 0) { throw "Camera channel result-reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelResultResetContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelResultResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel result-reset paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelStage = Join-Path $cameraChannelRoot 'stage-compiled-camera-channel-v1.eddgraph'
$cameraChannelStagePaste = Join-Path $cameraChannelRoot 'stage-compiled-camera-channel-v1-paste.eddgraph'
$cameraChannelStageRepeat = Join-Path $cameraChannelRoot 'stage-compiled-camera-channel-v1-repeat.eddgraph'
$cameraChannelStageRepeatPaste = Join-Path $cameraChannelRoot 'stage-compiled-camera-channel-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelStage, $cameraChannelStagePaste), @($cameraChannelStageRepeat, $cameraChannelStageRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelStageGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel staging generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelStage, $cameraChannelStageRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-compiled-camera-channel-v1.eddgraph')),
    @($cameraChannelStagePaste, $cameraChannelStageRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-compiled-camera-channel-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel staging generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelStage
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelStageContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelStage
if ($LASTEXITCODE -ne 0) { throw "Camera channel staging full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelStageContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelStagePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel staging paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelPublish = Join-Path $cameraChannelRoot 'publish-camera-channel-sample-v1.eddgraph'
$cameraChannelPublishPaste = Join-Path $cameraChannelRoot 'publish-camera-channel-sample-v1-paste.eddgraph'
$cameraChannelPublishRepeat = Join-Path $cameraChannelRoot 'publish-camera-channel-sample-v1-repeat.eddgraph'
$cameraChannelPublishRepeatPaste = Join-Path $cameraChannelRoot 'publish-camera-channel-sample-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelPublish, $cameraChannelPublishPaste), @($cameraChannelPublishRepeat, $cameraChannelPublishRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelPublishGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel publication generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelPublish, $cameraChannelPublishRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\publish-camera-channel-sample-v1.eddgraph')),
    @($cameraChannelPublishPaste, $cameraChannelPublishRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\publish-camera-channel-sample-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel publication generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelPublish
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelPublishContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelPublish
if ($LASTEXITCODE -ne 0) { throw "Camera channel publication full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelPublishContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelPublishPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel publication paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelEvaluate = Join-Path $cameraChannelRoot 'evaluate-camera-channel-assembly-v1.eddgraph'
$cameraChannelEvaluatePaste = Join-Path $cameraChannelRoot 'evaluate-camera-channel-assembly-v1-paste.eddgraph'
$cameraChannelEvaluateRepeat = Join-Path $cameraChannelRoot 'evaluate-camera-channel-assembly-v1-repeat.eddgraph'
$cameraChannelEvaluateRepeatPaste = Join-Path $cameraChannelRoot 'evaluate-camera-channel-assembly-v1-repeat-paste.eddgraph'
foreach ($pair in @(@($cameraChannelEvaluate, $cameraChannelEvaluatePaste), @($cameraChannelEvaluateRepeat, $cameraChannelEvaluateRepeatPaste))) {
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-CameraChannelEvaluateGraph.py') `
        --project-root $ProjectRoot --output $pair[0] --paste-output $pair[1]
    if ($LASTEXITCODE -ne 0) { throw "Camera channel evaluation generation failed with exit code $LASTEXITCODE." }
}
foreach ($comparison in @(
    @($cameraChannelEvaluate, $cameraChannelEvaluateRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-camera-channel-assembly-v1.eddgraph')),
    @($cameraChannelEvaluatePaste, $cameraChannelEvaluateRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-camera-channel-assembly-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw 'Camera channel evaluation generation is not byte deterministic.'
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $cameraChannelEvaluate
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelEvaluateContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelEvaluate
if ($LASTEXITCODE -ne 0) { throw "Camera channel evaluation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-CameraChannelEvaluateContracts.py') `
    --project-root $ProjectRoot --graph $cameraChannelEvaluatePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Camera channel evaluation paste contracts failed with exit code $LASTEXITCODE." }
$cameraChannelLiveStages = @(
    @('reset-camera-channel-compile-v1', 'Test-CameraChannelCompileResetContracts.py'),
    @('validate-camera-channel-inputs-v1', 'Test-CameraChannelValidationContracts.py'),
    @('compile-camera-channel-candidate-v1', 'Test-CameraChannelCandidateContracts.py'),
    @('commit-camera-channel-assembly-v1', 'Test-CameraChannelCommitContracts.py'),
    @('compile-camera-channel-assembly-v1', 'Test-CameraChannelCompileContracts.py'),
    @('reset-camera-channel-result-v1', 'Test-CameraChannelResultResetContracts.py'),
    @('stage-compiled-camera-channel-v1', 'Test-CameraChannelStageContracts.py'),
    @('publish-camera-channel-sample-v1', 'Test-CameraChannelPublishContracts.py'),
    @('evaluate-camera-channel-assembly-v1', 'Test-CameraChannelEvaluateContracts.py')
)
foreach ($stage in $cameraChannelLiveStages) {
    $live = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($stage[0]).eddgraph"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $live
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[1])") `
        --project-root $ProjectRoot --graph $live
    if ($LASTEXITCODE -ne 0) {
        throw "Live camera channel $($stage[0]) contracts failed with exit code $LASTEXITCODE."
    }
}
$documentAdapterNonce = [guid]::NewGuid().ToString('N')
$documentAdapterRoot = Join-Path $scratchRoot "edd-document-adapter-$documentAdapterNonce"
New-Item -ItemType Directory -Path $documentAdapterRoot -Force | Out-Null
$documentAdapterStages = @(
    @('reset-airframe-document-source-adapter-v2', 'Build-AirframeDocumentAdapterResetGraph.py', 'Test-AirframeDocumentAdapterResetContracts.py'),
    @('validate-airframe-document-source-adapter-v2', 'Build-AirframeDocumentAdapterValidationGraph.py', 'Test-AirframeDocumentAdapterValidationContracts.py'),
    @('commit-airframe-document-source-adapter-v2', 'Build-AirframeDocumentAdapterCommitGraph.py', 'Test-AirframeDocumentAdapterCommitContracts.py'),
    @('build-airframe-document-discontinuity-diagnostics-v2', 'Build-AirframeDocumentDiagnosticsGraph.py', 'Test-AirframeDocumentDiagnosticsContracts.py'),
    @('compile-airframe-document-source-adapter-v2', 'Build-AirframeDocumentAdapterCompileGraph.py', 'Test-AirframeDocumentAdapterCompileContracts.py')
)
foreach ($stage in $documentAdapterStages) {
    $generated = Join-Path $documentAdapterRoot "$($stage[0]).eddgraph"
    $generatedPaste = Join-Path $documentAdapterRoot "$($stage[0])-paste.eddgraph"
    $repeated = Join-Path $documentAdapterRoot "$($stage[0])-repeat.eddgraph"
    $repeatedPaste = Join-Path $documentAdapterRoot "$($stage[0])-repeat-paste.eddgraph"
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[1])") `
        --project-root $ProjectRoot --output $generated --paste-output $generatedPaste
    if ($LASTEXITCODE -ne 0) { throw "Document adapter $($stage[0]) generation failed with exit code $LASTEXITCODE." }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[1])") `
        --project-root $ProjectRoot --output $repeated --paste-output $repeatedPaste
    if ($LASTEXITCODE -ne 0) { throw "Repeated document adapter $($stage[0]) generation failed with exit code $LASTEXITCODE." }
    foreach ($comparison in @(
        @($generated, $repeated, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($stage[0]).eddgraph")),
        @($generatedPaste, $repeatedPaste, (Join-Path $ProjectRoot "tools\blueprint\snippets\$($stage[0])-paste.eddgraph"))
    )) {
        if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
            (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
            (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
            throw "Document adapter $($stage[0]) generation is not byte deterministic."
        }
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $generated
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[2])") `
        --project-root $ProjectRoot --graph $generated
    if ($LASTEXITCODE -ne 0) { throw "Document adapter $($stage[0]) full contracts failed with exit code $LASTEXITCODE." }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[2])") `
        --project-root $ProjectRoot --graph $generatedPaste --paste
    if ($LASTEXITCODE -ne 0) { throw "Document adapter $($stage[0]) paste contracts failed with exit code $LASTEXITCODE." }
    $live = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($stage[0]).eddgraph"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $live
    & python (Join-Path $ProjectRoot "tools\blueprint\$($stage[2])") `
        --project-root $ProjectRoot --graph $live
    if ($LASTEXITCODE -ne 0) { throw "Live document adapter $($stage[0]) contracts failed with exit code $LASTEXITCODE." }
}
$airframeSourceNonce = [guid]::NewGuid().ToString('N')
$airframeSourceRoot = Join-Path $scratchRoot "edd-airframe-source-$airframeSourceNonce"
New-Item -ItemType Directory -Path $airframeSourceRoot -Force | Out-Null
$sourceReset = Join-Path $airframeSourceRoot 'reset-airframe-source-sampling-v1.eddgraph'
$sourceResetPaste = Join-Path $airframeSourceRoot 'reset-airframe-source-sampling-v1-paste.eddgraph'
$sourceResetRepeat = Join-Path $airframeSourceRoot 'reset-airframe-source-sampling-v1-repeat.eddgraph'
$sourceResetRepeatPaste = Join-Path $airframeSourceRoot 'reset-airframe-source-sampling-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceSamplingResetGraph.py') `
    --project-root $ProjectRoot --output $sourceReset --paste-output $sourceResetPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source reset generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceSamplingResetGraph.py') `
    --project-root $ProjectRoot --output $sourceResetRepeat --paste-output $sourceResetRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source reset generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceReset, $sourceResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-source-sampling-v1.eddgraph')),
    @($sourceResetPaste, $sourceResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-source-sampling-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source reset generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceSamplingResetContracts.py') `
    --project-root $ProjectRoot --graph $sourceReset
if ($LASTEXITCODE -ne 0) { throw "Airframe source reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceSamplingResetContracts.py') `
    --project-root $ProjectRoot --graph $sourceResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source reset paste contracts failed with exit code $LASTEXITCODE." }

$sourceValidation = Join-Path $airframeSourceRoot 'validate-airframe-source-sampling-inputs-v1.eddgraph'
$sourceValidationPaste = Join-Path $airframeSourceRoot 'validate-airframe-source-sampling-inputs-v1-paste.eddgraph'
$sourceValidationRepeat = Join-Path $airframeSourceRoot 'validate-airframe-source-sampling-inputs-v1-repeat.eddgraph'
$sourceValidationRepeatPaste = Join-Path $airframeSourceRoot 'validate-airframe-source-sampling-inputs-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceSamplingValidationGraph.py') `
    --project-root $ProjectRoot --output $sourceValidation --paste-output $sourceValidationPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source validation generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceSamplingValidationGraph.py') `
    --project-root $ProjectRoot --output $sourceValidationRepeat --paste-output $sourceValidationRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source validation generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceValidation, $sourceValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-source-sampling-inputs-v1.eddgraph')),
    @($sourceValidationPaste, $sourceValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-source-sampling-inputs-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source validation generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceSamplingValidationContracts.py') `
    --project-root $ProjectRoot --graph $sourceValidation
if ($LASTEXITCODE -ne 0) { throw "Airframe source validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceSamplingValidationContracts.py') `
    --project-root $ProjectRoot --graph $sourceValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source validation paste contracts failed with exit code $LASTEXITCODE." }
$sourceComponents = Join-Path $airframeSourceRoot 'compile-airframe-source-position-profiles-v1.eddgraph'
$sourceComponentsPaste = Join-Path $airframeSourceRoot 'compile-airframe-source-position-profiles-v1-paste.eddgraph'
$sourceComponentsRepeat = Join-Path $airframeSourceRoot 'compile-airframe-source-position-profiles-v1-repeat.eddgraph'
$sourceComponentsRepeatPaste = Join-Path $airframeSourceRoot 'compile-airframe-source-position-profiles-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourcePositionProfilesGraph.py') `
    --project-root $ProjectRoot --output $sourceComponents --paste-output $sourceComponentsPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source component generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourcePositionProfilesGraph.py') `
    --project-root $ProjectRoot --output $sourceComponentsRepeat --paste-output $sourceComponentsRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source component generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceComponents, $sourceComponentsRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-source-position-profiles-v1.eddgraph')),
    @($sourceComponentsPaste, $sourceComponentsRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-source-position-profiles-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source component generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourcePositionProfilesContracts.py') `
    --project-root $ProjectRoot --graph $sourceComponents
if ($LASTEXITCODE -ne 0) { throw "Airframe source component full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourcePositionProfilesContracts.py') `
    --project-root $ProjectRoot --graph $sourceComponentsPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source component paste contracts failed with exit code $LASTEXITCODE." }
$sourceBodySamples = Join-Path $airframeSourceRoot 'build-airframe-source-position-body-profile-samples-v1.eddgraph'
$sourceBodySamplesPaste = Join-Path $airframeSourceRoot 'build-airframe-source-position-body-profile-samples-v1-paste.eddgraph'
$sourceBodySamplesRepeat = Join-Path $airframeSourceRoot 'build-airframe-source-position-body-profile-samples-v1-repeat.eddgraph'
$sourceBodySamplesRepeatPaste = Join-Path $airframeSourceRoot 'build-airframe-source-position-body-profile-samples-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourcePositionBodyProfileSamplesGraph.py') `
    --project-root $ProjectRoot --output $sourceBodySamples --paste-output $sourceBodySamplesPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source body/profile sample generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourcePositionBodyProfileSamplesGraph.py') `
    --project-root $ProjectRoot --output $sourceBodySamplesRepeat --paste-output $sourceBodySamplesRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source body/profile sample generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceBodySamples, $sourceBodySamplesRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-source-position-body-profile-samples-v1.eddgraph')),
    @($sourceBodySamplesPaste, $sourceBodySamplesRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-source-position-body-profile-samples-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source body/profile sample generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourcePositionBodyProfileSamplesContracts.py') `
    --project-root $ProjectRoot --graph $sourceBodySamples
if ($LASTEXITCODE -ne 0) { throw "Airframe source body/profile sample full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourcePositionBodyProfileSamplesContracts.py') `
    --project-root $ProjectRoot --graph $sourceBodySamplesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source body/profile sample paste contracts failed with exit code $LASTEXITCODE." }
$sourceGimbalSamples = Join-Path $airframeSourceRoot 'build-airframe-source-gimbal-samples-v1.eddgraph'
$sourceGimbalSamplesPaste = Join-Path $airframeSourceRoot 'build-airframe-source-gimbal-samples-v1-paste.eddgraph'
$sourceGimbalSamplesRepeat = Join-Path $airframeSourceRoot 'build-airframe-source-gimbal-samples-v1-repeat.eddgraph'
$sourceGimbalSamplesRepeatPaste = Join-Path $airframeSourceRoot 'build-airframe-source-gimbal-samples-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceGimbalSamplesGraph.py') `
    --project-root $ProjectRoot --output $sourceGimbalSamples --paste-output $sourceGimbalSamplesPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source gimbal sample generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceGimbalSamplesGraph.py') `
    --project-root $ProjectRoot --output $sourceGimbalSamplesRepeat --paste-output $sourceGimbalSamplesRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source gimbal sample generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceGimbalSamples, $sourceGimbalSamplesRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-source-gimbal-samples-v1.eddgraph')),
    @($sourceGimbalSamplesPaste, $sourceGimbalSamplesRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-source-gimbal-samples-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source gimbal sample generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceGimbalSamplesContracts.py') `
    --project-root $ProjectRoot --graph $sourceGimbalSamples
if ($LASTEXITCODE -ne 0) { throw "Airframe source gimbal sample full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceGimbalSamplesContracts.py') `
    --project-root $ProjectRoot --graph $sourceGimbalSamplesPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source gimbal sample paste contracts failed with exit code $LASTEXITCODE." }
$sourceCommit = Join-Path $airframeSourceRoot 'commit-airframe-source-samples-to-desired-v1.eddgraph'
$sourceCommitPaste = Join-Path $airframeSourceRoot 'commit-airframe-source-samples-to-desired-v1-paste.eddgraph'
$sourceCommitRepeat = Join-Path $airframeSourceRoot 'commit-airframe-source-samples-to-desired-v1-repeat.eddgraph'
$sourceCommitRepeatPaste = Join-Path $airframeSourceRoot 'commit-airframe-source-samples-to-desired-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceCommitGraph.py') `
    --project-root $ProjectRoot --output $sourceCommit --paste-output $sourceCommitPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source commit generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceCommitGraph.py') `
    --project-root $ProjectRoot --output $sourceCommitRepeat --paste-output $sourceCommitRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source commit generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceCommit, $sourceCommitRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-airframe-source-samples-to-desired-v1.eddgraph')),
    @($sourceCommitPaste, $sourceCommitRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-airframe-source-samples-to-desired-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source commit generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceCommitContracts.py') `
    --project-root $ProjectRoot --graph $sourceCommit
if ($LASTEXITCODE -ne 0) { throw "Airframe source commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceCommitContracts.py') `
    --project-root $ProjectRoot --graph $sourceCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source commit paste contracts failed with exit code $LASTEXITCODE." }
$sourceCompile = Join-Path $airframeSourceRoot 'compile-airframe-source-sampling-v1.eddgraph'
$sourceCompilePaste = Join-Path $airframeSourceRoot 'compile-airframe-source-sampling-v1-paste.eddgraph'
$sourceCompileRepeat = Join-Path $airframeSourceRoot 'compile-airframe-source-sampling-v1-repeat.eddgraph'
$sourceCompileRepeatPaste = Join-Path $airframeSourceRoot 'compile-airframe-source-sampling-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceCompileGraph.py') `
    --project-root $ProjectRoot --output $sourceCompile --paste-output $sourceCompilePaste
if ($LASTEXITCODE -ne 0) { throw "Airframe source compile generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeSourceCompileGraph.py') `
    --project-root $ProjectRoot --output $sourceCompileRepeat --paste-output $sourceCompileRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe source compile generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($sourceCompile, $sourceCompileRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-source-sampling-v1.eddgraph')),
    @($sourceCompilePaste, $sourceCompileRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-source-sampling-v1-paste.eddgraph'))
)) {
    if ((Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[1] -Algorithm SHA256).Hash -or
        (Get-FileHash -LiteralPath $comparison[0] -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $comparison[2] -Algorithm SHA256).Hash) {
        throw "Airframe source compile generation is not byte deterministic."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $comparison[0]
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceCompileContracts.py') `
    --project-root $ProjectRoot --graph $sourceCompile
if ($LASTEXITCODE -ne 0) { throw "Airframe source compile full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeSourceCompileContracts.py') `
    --project-root $ProjectRoot --graph $sourceCompilePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Airframe source compile paste contracts failed with exit code $LASTEXITCODE." }
$airframeSourceLiveContracts = @(
    @('reset-airframe-source-sampling-v1.eddgraph', 'Test-AirframeSourceSamplingResetContracts.py'),
    @('validate-airframe-source-sampling-inputs-v1.eddgraph', 'Test-AirframeSourceSamplingValidationContracts.py'),
    @('compile-airframe-source-position-profiles-v1.eddgraph', 'Test-AirframeSourcePositionProfilesContracts.py'),
    @('build-airframe-source-position-body-profile-samples-v1.eddgraph', 'Test-AirframeSourcePositionBodyProfileSamplesContracts.py'),
    @('build-airframe-source-gimbal-samples-v1.eddgraph', 'Test-AirframeSourceGimbalSamplesContracts.py'),
    @('commit-airframe-source-samples-to-desired-v1.eddgraph', 'Test-AirframeSourceCommitContracts.py'),
    @('compile-airframe-source-sampling-v1.eddgraph', 'Test-AirframeSourceCompileContracts.py')
)
foreach ($liveContract in $airframeSourceLiveContracts) {
    $liveGraph = Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($liveContract[0])"
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $liveGraph
    & python (Join-Path $ProjectRoot "tools\blueprint\$($liveContract[1])") `
        --project-root $ProjectRoot --graph $liveGraph
    if ($LASTEXITCODE -ne 0) {
        throw "Live airframe source graph contract failed for $($liveContract[0]) with exit code $LASTEXITCODE."
    }
}
$airframeDesiredNonce = [guid]::NewGuid().ToString('N')
$airframeDesiredRoot = Join-Path $scratchRoot "edd-airframe-desired-$airframeDesiredNonce"
New-Item -ItemType Directory -Path $airframeDesiredRoot -Force | Out-Null
$desiredReset = Join-Path $airframeDesiredRoot 'reset-airframe-desired-stream-v1.eddgraph'
$desiredResetPaste = Join-Path $airframeDesiredRoot 'reset-airframe-desired-stream-v1-paste.eddgraph'
$desiredResetRepeat = Join-Path $airframeDesiredRoot 'reset-airframe-desired-stream-v1-repeat.eddgraph'
$desiredResetRepeatPaste = Join-Path $airframeDesiredRoot 'reset-airframe-desired-stream-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamResetGraph.py') `
    --project-root $ProjectRoot --output $desiredReset --paste-output $desiredResetPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream reset generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamResetGraph.py') `
    --project-root $ProjectRoot --output $desiredResetRepeat --paste-output $desiredResetRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired-stream reset generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($desiredReset, $desiredResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-desired-stream-v1.eddgraph')),
    @($desiredResetPaste, $desiredResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-desired-stream-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired-stream reset generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($desiredReset, $false),
    @($desiredResetPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\reset-airframe-desired-stream-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredStreamResetContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream reset contracts failed with exit code $LASTEXITCODE." }
}
$desiredValidation = Join-Path $airframeDesiredRoot 'validate-airframe-desired-stream-inputs-v1.eddgraph'
$desiredValidationPaste = Join-Path $airframeDesiredRoot 'validate-airframe-desired-stream-inputs-v1-paste.eddgraph'
$desiredValidationRepeat = Join-Path $airframeDesiredRoot 'validate-airframe-desired-stream-inputs-v1-repeat.eddgraph'
$desiredValidationRepeatPaste = Join-Path $airframeDesiredRoot 'validate-airframe-desired-stream-inputs-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamValidationGraph.py') `
    --project-root $ProjectRoot --output $desiredValidation --paste-output $desiredValidationPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream validation generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamValidationGraph.py') `
    --project-root $ProjectRoot --output $desiredValidationRepeat --paste-output $desiredValidationRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired-stream validation generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($desiredValidation, $desiredValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-desired-stream-inputs-v1.eddgraph')),
    @($desiredValidationPaste, $desiredValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-desired-stream-inputs-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired-stream validation generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($desiredValidation, $false),
    @($desiredValidationPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\validate-airframe-desired-stream-inputs-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredStreamValidationContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream validation contracts failed with exit code $LASTEXITCODE." }
}
foreach ($derivativeStage in @('velocity', 'acceleration', 'jerk')) {
    $derivativeSlug = "build-airframe-desired-$derivativeStage-samples-v1"
    $derivativeGraph = Join-Path $airframeDesiredRoot "$derivativeSlug.eddgraph"
    $derivativePaste = Join-Path $airframeDesiredRoot "$derivativeSlug-paste.eddgraph"
    $derivativeRepeat = Join-Path $airframeDesiredRoot "$derivativeSlug-repeat.eddgraph"
    $derivativeRepeatPaste = Join-Path $airframeDesiredRoot "$derivativeSlug-repeat-paste.eddgraph"
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredDerivativeGraph.py') `
        --project-root $ProjectRoot --stage $derivativeStage --output $derivativeGraph --paste-output $derivativePaste
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired $derivativeStage generation failed with exit code $LASTEXITCODE." }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredDerivativeGraph.py') `
        --project-root $ProjectRoot --stage $derivativeStage --output $derivativeRepeat --paste-output $derivativeRepeatPaste
    if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired $derivativeStage generation failed with exit code $LASTEXITCODE." }
    foreach ($comparison in @(
        @($derivativeGraph, $derivativeRepeat, (Join-Path $ProjectRoot "tools\blueprint\snippets\$derivativeSlug.eddgraph")),
        @($derivativePaste, $derivativeRepeatPaste, (Join-Path $ProjectRoot "tools\blueprint\snippets\$derivativeSlug-paste.eddgraph"))
    )) {
        $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
        if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired $derivativeStage generation is not byte-identical." }
    }
    foreach ($graphCase in @(
        @($derivativeGraph, $false),
        @($derivativePaste, $true),
        @((Join-Path $ProjectRoot "tools\blueprint\live-snippets\$derivativeSlug.eddgraph"), $false)
    )) {
        & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
        $arguments = @('--project-root', $ProjectRoot, '--stage', $derivativeStage, '--graph', $graphCase[0])
        if ($graphCase[1]) { $arguments += '--paste' }
        & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredDerivativeContracts.py') @arguments
        if ($LASTEXITCODE -ne 0) { throw "Airframe desired $derivativeStage contracts failed with exit code $LASTEXITCODE." }
    }
}
$velocitySampler = Join-Path $airframeDesiredRoot 'sample-airframe-desired-velocity-at-time-v1.eddgraph'
$velocitySamplerPaste = Join-Path $airframeDesiredRoot 'sample-airframe-desired-velocity-at-time-v1-paste.eddgraph'
$velocitySamplerRepeat = Join-Path $airframeDesiredRoot 'sample-airframe-desired-velocity-at-time-v1-repeat.eddgraph'
$velocitySamplerRepeatPaste = Join-Path $airframeDesiredRoot 'sample-airframe-desired-velocity-at-time-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredVelocitySamplerGraph.py') `
    --project-root $ProjectRoot --output $velocitySampler --paste-output $velocitySamplerPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired velocity sampler generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredVelocitySamplerGraph.py') `
    --project-root $ProjectRoot --output $velocitySamplerRepeat --paste-output $velocitySamplerRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired velocity sampler generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($velocitySampler, $velocitySamplerRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\sample-airframe-desired-velocity-at-time-v1.eddgraph')),
    @($velocitySamplerPaste, $velocitySamplerRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\sample-airframe-desired-velocity-at-time-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired velocity sampler generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($velocitySampler, $false),
    @($velocitySamplerPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\sample-airframe-desired-velocity-at-time-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredVelocitySamplerContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired velocity sampler contracts failed with exit code $LASTEXITCODE." }
}
$poseSamples = Join-Path $airframeDesiredRoot 'solve-airframe-desired-pose-samples-v1.eddgraph'
$poseSamplesPaste = Join-Path $airframeDesiredRoot 'solve-airframe-desired-pose-samples-v1-paste.eddgraph'
$poseSamplesRepeat = Join-Path $airframeDesiredRoot 'solve-airframe-desired-pose-samples-v1-repeat.eddgraph'
$poseSamplesRepeatPaste = Join-Path $airframeDesiredRoot 'solve-airframe-desired-pose-samples-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredPoseSamplesGraph.py') `
    --project-root $ProjectRoot --output $poseSamples --paste-output $poseSamplesPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired pose-sample generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredPoseSamplesGraph.py') `
    --project-root $ProjectRoot --output $poseSamplesRepeat --paste-output $poseSamplesRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired pose-sample generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($poseSamples, $poseSamplesRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\solve-airframe-desired-pose-samples-v1.eddgraph')),
    @($poseSamplesPaste, $poseSamplesRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\solve-airframe-desired-pose-samples-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired pose-sample generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($poseSamples, $false),
    @($poseSamplesPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\solve-airframe-desired-pose-samples-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredPoseSamplesContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired pose-sample contracts failed with exit code $LASTEXITCODE." }
}
$desiredCommit = Join-Path $airframeDesiredRoot 'commit-airframe-desired-stream-to-prebake-v1.eddgraph'
$desiredCommitPaste = Join-Path $airframeDesiredRoot 'commit-airframe-desired-stream-to-prebake-v1-paste.eddgraph'
$desiredCommitRepeat = Join-Path $airframeDesiredRoot 'commit-airframe-desired-stream-to-prebake-v1-repeat.eddgraph'
$desiredCommitRepeatPaste = Join-Path $airframeDesiredRoot 'commit-airframe-desired-stream-to-prebake-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamCommitGraph.py') --project-root $ProjectRoot --output $desiredCommit --paste-output $desiredCommitPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream commit generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamCommitGraph.py') --project-root $ProjectRoot --output $desiredCommitRepeat --paste-output $desiredCommitRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired-stream commit generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($desiredCommit, $desiredCommitRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-airframe-desired-stream-to-prebake-v1.eddgraph')),
    @($desiredCommitPaste, $desiredCommitRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-airframe-desired-stream-to-prebake-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired-stream commit generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($desiredCommit, $false),
    @($desiredCommitPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\commit-airframe-desired-stream-to-prebake-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0]); if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredStreamCommitContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream commit contracts failed with exit code $LASTEXITCODE." }
}
$desiredCompile = Join-Path $airframeDesiredRoot 'compile-airframe-desired-stream-v1.eddgraph'
$desiredCompilePaste = Join-Path $airframeDesiredRoot 'compile-airframe-desired-stream-v1-paste.eddgraph'
$desiredCompileRepeat = Join-Path $airframeDesiredRoot 'compile-airframe-desired-stream-v1-repeat.eddgraph'
$desiredCompileRepeatPaste = Join-Path $airframeDesiredRoot 'compile-airframe-desired-stream-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamCompileGraph.py') --project-root $ProjectRoot --output $desiredCompile --paste-output $desiredCompilePaste
if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream orchestration generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeDesiredStreamCompileGraph.py') --project-root $ProjectRoot --output $desiredCompileRepeat --paste-output $desiredCompileRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe desired-stream orchestration generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($desiredCompile, $desiredCompileRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-desired-stream-v1.eddgraph')),
    @($desiredCompilePaste, $desiredCompileRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-desired-stream-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe desired-stream orchestration generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($desiredCompile, $false),
    @($desiredCompilePaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\compile-airframe-desired-stream-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0]); if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeDesiredStreamCompileContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe desired-stream orchestration contracts failed with exit code $LASTEXITCODE." }
}
$airframePrebakeNonce = [guid]::NewGuid().ToString('N')
$airframePrebakeRoot = Join-Path $scratchRoot "edd-airframe-prebake-$airframePrebakeNonce"
$airframePrebakeReset = Join-Path $airframePrebakeRoot 'reset-airframe-prebake-candidate-v1.eddgraph'
$airframePrebakeResetPaste = Join-Path $airframePrebakeRoot 'reset-airframe-prebake-candidate-v1-paste.eddgraph'
$airframePrebakeResetRepeat = Join-Path $airframePrebakeRoot 'reset-airframe-prebake-candidate-v1-repeat.eddgraph'
$airframePrebakeResetRepeatPaste = Join-Path $airframePrebakeRoot 'reset-airframe-prebake-candidate-v1-repeat-paste.eddgraph'
New-Item -ItemType Directory -Path $airframePrebakeRoot -Force | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeResetGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeReset --paste-output $airframePrebakeResetPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake reset generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeResetGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeResetRepeat --paste-output $airframePrebakeResetRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake reset generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeReset, $airframePrebakeResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-prebake-candidate-v1.eddgraph')),
    @($airframePrebakeResetPaste, $airframePrebakeResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-prebake-candidate-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake reset generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeReset, $false), @($airframePrebakeResetPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeResetContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake reset contracts failed with exit code $LASTEXITCODE." }
}
$airframePrebakeValidation = Join-Path $airframePrebakeRoot 'validate-airframe-prebake-inputs-v1.eddgraph'
$airframePrebakeValidationPaste = Join-Path $airframePrebakeRoot 'validate-airframe-prebake-inputs-v1-paste.eddgraph'
$airframePrebakeValidationRepeat = Join-Path $airframePrebakeRoot 'validate-airframe-prebake-inputs-v1-repeat.eddgraph'
$airframePrebakeValidationRepeatPaste = Join-Path $airframePrebakeRoot 'validate-airframe-prebake-inputs-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeValidationGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeValidation --paste-output $airframePrebakeValidationPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake validation generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeValidationGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeValidationRepeat --paste-output $airframePrebakeValidationRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake validation generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeValidation, $airframePrebakeValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-prebake-inputs-v1.eddgraph')),
    @($airframePrebakeValidationPaste, $airframePrebakeValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-prebake-inputs-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake validation generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeValidation, $false), @($airframePrebakeValidationPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeValidationContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake validation contracts failed with exit code $LASTEXITCODE." }
}
$airframePrebakeNative = Join-Path $airframePrebakeRoot 'airframe-prebake-native-node-forms.eddgraph'
$airframePrebakeNativeRepeat = Join-Path $airframePrebakeRoot 'airframe-prebake-native-node-forms-repeat.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeNativeNodeForms.py') `
    --project-root $ProjectRoot --output $airframePrebakeNative
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake native form generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeNativeNodeForms.py') `
    --project-root $ProjectRoot --output $airframePrebakeNativeRepeat
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake native form generation failed with exit code $LASTEXITCODE." }
$airframePrebakeNativeChecked = Join-Path $ProjectRoot 'tools\blueprint\templates\airframe-prebake-native-node-forms.eddgraph'
$nativeHashes = @($airframePrebakeNative, $airframePrebakeNativeRepeat, $airframePrebakeNativeChecked) |
    ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
if (@($nativeHashes | Select-Object -Unique).Count -ne 1) {
    throw "Airframe prebake native form generation is not byte-identical."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $airframePrebakeNative
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeNativeNodeForms.py') `
    --project-root $ProjectRoot --graph $airframePrebakeNative
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake native form contracts failed with exit code $LASTEXITCODE." }

$airframeRateLimit = Join-Path $airframePrebakeRoot 'apply-airframe-angular-rate-limit-v1.eddgraph'
$airframeRateLimitPaste = Join-Path $airframePrebakeRoot 'apply-airframe-angular-rate-limit-v1-paste.eddgraph'
$airframeRateLimitRepeat = Join-Path $airframePrebakeRoot 'apply-airframe-angular-rate-limit-v1-repeat.eddgraph'
$airframeRateLimitRepeatPaste = Join-Path $airframePrebakeRoot 'apply-airframe-angular-rate-limit-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeAngularRateLimitGraph.py') `
    --project-root $ProjectRoot --output $airframeRateLimit --paste-output $airframeRateLimitPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe angular-rate helper generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeAngularRateLimitGraph.py') `
    --project-root $ProjectRoot --output $airframeRateLimitRepeat --paste-output $airframeRateLimitRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe angular-rate helper generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframeRateLimit, $airframeRateLimitRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-airframe-angular-rate-limit-v1.eddgraph')),
    @($airframeRateLimitPaste, $airframeRateLimitRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\apply-airframe-angular-rate-limit-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe angular-rate helper generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframeRateLimit, $false), @($airframeRateLimitPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeAngularRateLimitContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe angular-rate helper contracts failed with exit code $LASTEXITCODE." }
}
$airframePrebakeSamples = Join-Path $airframePrebakeRoot 'build-airframe-prebake-samples-v1.eddgraph'
$airframePrebakeSamplesPaste = Join-Path $airframePrebakeRoot 'build-airframe-prebake-samples-v1-paste.eddgraph'
$airframePrebakeSamplesRepeat = Join-Path $airframePrebakeRoot 'build-airframe-prebake-samples-v1-repeat.eddgraph'
$airframePrebakeSamplesRepeatPaste = Join-Path $airframePrebakeRoot 'build-airframe-prebake-samples-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeSamplesGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeSamples --paste-output $airframePrebakeSamplesPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake sample-builder generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeSamplesGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeSamplesRepeat --paste-output $airframePrebakeSamplesRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake sample-builder generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeSamples, $airframePrebakeSamplesRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-prebake-samples-v1.eddgraph')),
    @($airframePrebakeSamplesPaste, $airframePrebakeSamplesRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\build-airframe-prebake-samples-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake sample-builder generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeSamples, $false), @($airframePrebakeSamplesPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeSamplesContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake sample-builder contracts failed with exit code $LASTEXITCODE." }
}

$airframePrebakeCommit = Join-Path $airframePrebakeRoot 'commit-compiled-airframe-prebake-v1.eddgraph'
$airframePrebakeCommitPaste = Join-Path $airframePrebakeRoot 'commit-compiled-airframe-prebake-v1-paste.eddgraph'
$airframePrebakeCommitRepeat = Join-Path $airframePrebakeRoot 'commit-compiled-airframe-prebake-v1-repeat.eddgraph'
$airframePrebakeCommitRepeatPaste = Join-Path $airframePrebakeRoot 'commit-compiled-airframe-prebake-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeCommitGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeCommit --paste-output $airframePrebakeCommitPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake commit generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeCommitGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeCommitRepeat --paste-output $airframePrebakeCommitRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake commit generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeCommit, $airframePrebakeCommitRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-compiled-airframe-prebake-v1.eddgraph')),
    @($airframePrebakeCommitPaste, $airframePrebakeCommitRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\commit-compiled-airframe-prebake-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake commit generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeCommit, $false), @($airframePrebakeCommitPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeCommitContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake commit contracts failed with exit code $LASTEXITCODE." }
}

$airframePrebakeCompile = Join-Path $airframePrebakeRoot 'compile-airframe-prebake-v1.eddgraph'
$airframePrebakeCompilePaste = Join-Path $airframePrebakeRoot 'compile-airframe-prebake-v1-paste.eddgraph'
$airframePrebakeCompileRepeat = Join-Path $airframePrebakeRoot 'compile-airframe-prebake-v1-repeat.eddgraph'
$airframePrebakeCompileRepeatPaste = Join-Path $airframePrebakeRoot 'compile-airframe-prebake-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeCompileGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeCompile --paste-output $airframePrebakeCompilePaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake compile generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeCompileGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeCompileRepeat --paste-output $airframePrebakeCompileRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake compile generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeCompile, $airframePrebakeCompileRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-prebake-v1.eddgraph')),
    @($airframePrebakeCompilePaste, $airframePrebakeCompileRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\compile-airframe-prebake-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake compile generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeCompile, $false), @($airframePrebakeCompilePaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeCompileContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake compile contracts failed with exit code $LASTEXITCODE." }
}

$airframePrebakeEvaluator = Join-Path $airframePrebakeRoot 'evaluate-compiled-airframe-prebake-v1.eddgraph'
$airframePrebakeEvaluatorPaste = Join-Path $airframePrebakeRoot 'evaluate-compiled-airframe-prebake-v1-paste.eddgraph'
$airframePrebakeEvaluatorRepeat = Join-Path $airframePrebakeRoot 'evaluate-compiled-airframe-prebake-v1-repeat.eddgraph'
$airframePrebakeEvaluatorRepeatPaste = Join-Path $airframePrebakeRoot 'evaluate-compiled-airframe-prebake-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeEvaluator --paste-output $airframePrebakeEvaluatorPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe prebake evaluator generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframePrebakeEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $airframePrebakeEvaluatorRepeat --paste-output $airframePrebakeEvaluatorRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe prebake evaluator generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframePrebakeEvaluator, $airframePrebakeEvaluatorRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-compiled-airframe-prebake-v1.eddgraph')),
    @($airframePrebakeEvaluatorPaste, $airframePrebakeEvaluatorRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-compiled-airframe-prebake-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe prebake evaluator generation is not byte-identical." }
}
foreach ($graphCase in @(@($airframePrebakeEvaluator, $false), @($airframePrebakeEvaluatorPaste, $true))) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframePrebakeEvaluatorContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe prebake evaluator contracts failed with exit code $LASTEXITCODE." }
}

$airframeGimbalNonce = [guid]::NewGuid().ToString('N')
$airframeGimbalRoot = Join-Path $scratchRoot "edd-airframe-gimbal-$airframeGimbalNonce"
$airframeGimbalReset = Join-Path $airframeGimbalRoot 'reset-airframe-gimbal-v1.eddgraph'
$airframeGimbalResetPaste = Join-Path $airframeGimbalRoot 'reset-airframe-gimbal-v1-paste.eddgraph'
$airframeGimbalResetRepeat = Join-Path $airframeGimbalRoot 'reset-airframe-gimbal-v1-repeat.eddgraph'
$airframeGimbalResetRepeatPaste = Join-Path $airframeGimbalRoot 'reset-airframe-gimbal-v1-repeat-paste.eddgraph'
New-Item -ItemType Directory -Path $airframeGimbalRoot -Force | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalResetGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalReset --paste-output $airframeGimbalResetPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal reset graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalResetGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalResetRepeat --paste-output $airframeGimbalResetRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe/gimbal reset generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframeGimbalReset, $airframeGimbalResetRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-gimbal-v1.eddgraph')),
    @($airframeGimbalResetPaste, $airframeGimbalResetRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-airframe-gimbal-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe/gimbal reset generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($airframeGimbalReset, $false),
    @($airframeGimbalResetPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\reset-airframe-gimbal-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeGimbalResetContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal reset contracts failed with exit code $LASTEXITCODE." }
}
$airframeGimbalValidation = Join-Path $airframeGimbalRoot 'validate-airframe-gimbal-inputs-v1.eddgraph'
$airframeGimbalValidationPaste = Join-Path $airframeGimbalRoot 'validate-airframe-gimbal-inputs-v1-paste.eddgraph'
$airframeGimbalValidationRepeat = Join-Path $airframeGimbalRoot 'validate-airframe-gimbal-inputs-v1-repeat.eddgraph'
$airframeGimbalValidationRepeatPaste = Join-Path $airframeGimbalRoot 'validate-airframe-gimbal-inputs-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalValidationGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalValidation --paste-output $airframeGimbalValidationPaste
if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal validation graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalValidationGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalValidationRepeat --paste-output $airframeGimbalValidationRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe/gimbal validation generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframeGimbalValidation, $airframeGimbalValidationRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-gimbal-inputs-v1.eddgraph')),
    @($airframeGimbalValidationPaste, $airframeGimbalValidationRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-airframe-gimbal-inputs-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe/gimbal validation generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($airframeGimbalValidation, $false),
    @($airframeGimbalValidationPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\validate-airframe-gimbal-inputs-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeGimbalValidationContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal validation contracts failed with exit code $LASTEXITCODE." }
}
$airframeGimbalNative = Join-Path $airframeGimbalRoot 'airframe-gimbal-native-node-forms.eddgraph'
$airframeGimbalNativeRepeat = Join-Path $airframeGimbalRoot 'airframe-gimbal-native-node-forms-repeat.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalNativeNodeForms.py') `
    --project-root $ProjectRoot --output $airframeGimbalNative
if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal native form generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalNativeNodeForms.py') `
    --project-root $ProjectRoot --output $airframeGimbalNativeRepeat
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe/gimbal native form generation failed with exit code $LASTEXITCODE." }
$airframeGimbalNativeChecked = Join-Path $ProjectRoot 'tools\blueprint\templates\airframe-gimbal-native-node-forms.eddgraph'
$nativeHashes = @($airframeGimbalNative, $airframeGimbalNativeRepeat, $airframeGimbalNativeChecked) |
    ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
if (@($nativeHashes | Select-Object -Unique).Count -ne 1) { throw "Airframe/gimbal native form generation is not byte-identical." }
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $airframeGimbalNative
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeGimbalNativeNodeForms.py') `
    --project-root $ProjectRoot --graph $airframeGimbalNative
if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal native form contracts failed with exit code $LASTEXITCODE." }

$airframeGimbalSolve = Join-Path $airframeGimbalRoot 'solve-airframe-gimbal-v1.eddgraph'
$airframeGimbalSolvePaste = Join-Path $airframeGimbalRoot 'solve-airframe-gimbal-v1-paste.eddgraph'
$airframeGimbalSolveRepeat = Join-Path $airframeGimbalRoot 'solve-airframe-gimbal-v1-repeat.eddgraph'
$airframeGimbalSolveRepeatPaste = Join-Path $airframeGimbalRoot 'solve-airframe-gimbal-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalSolveGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalSolve --paste-output $airframeGimbalSolvePaste
if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal solve graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-AirframeGimbalSolveGraph.py') `
    --project-root $ProjectRoot --output $airframeGimbalSolveRepeat --paste-output $airframeGimbalSolveRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated airframe/gimbal solve generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($airframeGimbalSolve, $airframeGimbalSolveRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\solve-airframe-gimbal-v1.eddgraph')),
    @($airframeGimbalSolvePaste, $airframeGimbalSolveRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\solve-airframe-gimbal-v1-paste.eddgraph'))
)) {
    $hashes = $comparison | ForEach-Object { (Get-FileHash -Algorithm SHA256 $_).Hash }
    if (@($hashes | Select-Object -Unique).Count -ne 1) { throw "Airframe/gimbal solve generation is not byte-identical." }
}
foreach ($graphCase in @(
    @($airframeGimbalSolve, $false),
    @($airframeGimbalSolvePaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\solve-airframe-gimbal-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graphCase[0]
    $arguments = @('--project-root', $ProjectRoot, '--graph', $graphCase[0])
    if ($graphCase[1]) { $arguments += '--paste' }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-AirframeGimbalSolveContracts.py') @arguments
    if ($LASTEXITCODE -ne 0) { throw "Airframe/gimbal solve contracts failed with exit code $LASTEXITCODE." }
}

$cinematicPoseNonce = [guid]::NewGuid().ToString('N')
$cinematicPoseRoot = Join-Path $scratchRoot "edd-cinematic-pose-$cinematicPoseNonce"
$cinematicPoseReset = Join-Path $cinematicPoseRoot 'reset-cinematic-pose-v1.eddgraph'
$cinematicPoseResetPaste = Join-Path $cinematicPoseRoot 'reset-cinematic-pose-v1-paste.eddgraph'
$cinematicPoseResetRepeat = Join-Path $cinematicPoseRoot 'reset-cinematic-pose-v1-repeat.eddgraph'
$cinematicPoseResetRepeatPaste = Join-Path $cinematicPoseRoot 'reset-cinematic-pose-v1-repeat-paste.eddgraph'
$cinematicPoseValidation = Join-Path $cinematicPoseRoot 'validate-cinematic-pose-inputs-v1.eddgraph'
$cinematicPoseValidationPaste = Join-Path $cinematicPoseRoot 'validate-cinematic-pose-inputs-v1-paste.eddgraph'
$cinematicPoseValidationRepeat = Join-Path $cinematicPoseRoot 'validate-cinematic-pose-inputs-v1-repeat.eddgraph'
$cinematicPoseValidationRepeatPaste = Join-Path $cinematicPoseRoot 'validate-cinematic-pose-inputs-v1-repeat-paste.eddgraph'
$cinematicPoseCommit = Join-Path $cinematicPoseRoot 'commit-compiled-cinematic-pose-v1.eddgraph'
$cinematicPoseCommitPaste = Join-Path $cinematicPoseRoot 'commit-compiled-cinematic-pose-v1-paste.eddgraph'
$cinematicPoseCommitRepeat = Join-Path $cinematicPoseRoot 'commit-compiled-cinematic-pose-v1-repeat.eddgraph'
$cinematicPoseCommitRepeatPaste = Join-Path $cinematicPoseRoot 'commit-compiled-cinematic-pose-v1-repeat-paste.eddgraph'
$cinematicPoseCompile = Join-Path $cinematicPoseRoot 'compile-cinematic-pose-v1.eddgraph'
$cinematicPoseCompilePaste = Join-Path $cinematicPoseRoot 'compile-cinematic-pose-v1-paste.eddgraph'
$cinematicPoseCompileRepeat = Join-Path $cinematicPoseRoot 'compile-cinematic-pose-v1-repeat.eddgraph'
$cinematicPoseCompileRepeatPaste = Join-Path $cinematicPoseRoot 'compile-cinematic-pose-v1-repeat-paste.eddgraph'
$cinematicPoseEvaluator = Join-Path $cinematicPoseRoot 'evaluate-compiled-cinematic-pose-v1.eddgraph'
$cinematicPoseEvaluatorPaste = Join-Path $cinematicPoseRoot 'evaluate-compiled-cinematic-pose-v1-paste.eddgraph'
$cinematicPoseEvaluatorRepeat = Join-Path $cinematicPoseRoot 'evaluate-compiled-cinematic-pose-v1-repeat.eddgraph'
$cinematicPoseEvaluatorRepeatPaste = Join-Path $cinematicPoseRoot 'evaluate-compiled-cinematic-pose-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CinematicPoseResetGraph.py') `
    --project-root $ProjectRoot --output $cinematicPoseReset --paste-output $cinematicPoseResetPaste
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic pose reset graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CinematicPoseResetGraph.py') `
    --project-root $ProjectRoot --output $cinematicPoseResetRepeat --paste-output $cinematicPoseResetRepeatPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repeated cinematic pose reset graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CinematicPoseValidationGraph.py') `
    --project-root $ProjectRoot --output $cinematicPoseValidation --paste-output $cinematicPoseValidationPaste
if ($LASTEXITCODE -ne 0) {
    throw "Cinematic pose validation graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-CinematicPoseValidationGraph.py') `
    --project-root $ProjectRoot --output $cinematicPoseValidationRepeat --paste-output $cinematicPoseValidationRepeatPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repeated cinematic pose validation graph generation failed with exit code $LASTEXITCODE."
}
foreach ($spec in @(
    @('Build-CinematicPoseCommitGraph.py', $cinematicPoseCommit, $cinematicPoseCommitPaste, $cinematicPoseCommitRepeat, $cinematicPoseCommitRepeatPaste),
    @('Build-CinematicPoseCompileGraph.py', $cinematicPoseCompile, $cinematicPoseCompilePaste, $cinematicPoseCompileRepeat, $cinematicPoseCompileRepeatPaste),
    @('Build-CinematicPoseEvaluatorGraph.py', $cinematicPoseEvaluator, $cinematicPoseEvaluatorPaste, $cinematicPoseEvaluatorRepeat, $cinematicPoseEvaluatorRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec[0])") `
        --project-root $ProjectRoot --output $spec[1] --paste-output $spec[2]
    if ($LASTEXITCODE -ne 0) {
        throw "Cinematic pose graph generation failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec[0])") `
        --project-root $ProjectRoot --output $spec[3] --paste-output $spec[4]
    if ($LASTEXITCODE -ne 0) {
        throw "Repeated cinematic pose graph generation failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}
foreach ($pair in @(
    @($cinematicPoseReset, $cinematicPoseResetRepeat),
    @($cinematicPoseResetPaste, $cinematicPoseResetRepeatPaste),
    @($cinematicPoseValidation, $cinematicPoseValidationRepeat),
    @($cinematicPoseValidationPaste, $cinematicPoseValidationRepeatPaste),
    @($cinematicPoseCommit, $cinematicPoseCommitRepeat),
    @($cinematicPoseCommitPaste, $cinematicPoseCommitRepeatPaste),
    @($cinematicPoseCompile, $cinematicPoseCompileRepeat),
    @($cinematicPoseCompilePaste, $cinematicPoseCompileRepeatPaste),
    @($cinematicPoseEvaluator, $cinematicPoseEvaluatorRepeat),
    @($cinematicPoseEvaluatorPaste, $cinematicPoseEvaluatorRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Cinematic pose reset graph generation is not deterministic: $($pair[0])"
    }
}
foreach ($spec in @(
    @($cinematicPoseReset, $false),
    @($cinematicPoseResetPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-cinematic-pose-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-cinematic-pose-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\reset-cinematic-pose-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-CinematicPoseResetContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Cinematic pose reset contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}
foreach ($spec in @(
    @($cinematicPoseValidation, $false),
    @($cinematicPoseValidationPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-cinematic-pose-inputs-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\validate-cinematic-pose-inputs-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\validate-cinematic-pose-inputs-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-CinematicPoseValidationContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Cinematic pose validation contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}
foreach ($family in @(
    @('Commit', 'Test-CinematicPoseCommitContracts.py', $cinematicPoseCommit, $cinematicPoseCommitPaste, 'commit-compiled-cinematic-pose-v1'),
    @('Compile', 'Test-CinematicPoseCompileContracts.py', $cinematicPoseCompile, $cinematicPoseCompilePaste, 'compile-cinematic-pose-v1'),
    @('Evaluator', 'Test-CinematicPoseEvaluatorContracts.py', $cinematicPoseEvaluator, $cinematicPoseEvaluatorPaste, 'evaluate-compiled-cinematic-pose-v1')
)) {
    foreach ($spec in @(
        @($family[2], $false),
        @($family[3], $true),
        @((Join-Path $ProjectRoot "tools\blueprint\snippets\$($family[4]).eddgraph"), $false),
        @((Join-Path $ProjectRoot "tools\blueprint\snippets\$($family[4])-paste.eddgraph"), $true),
        @((Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($family[4]).eddgraph"), $false)
    )) {
        & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
        $arguments = @(
            (Join-Path $ProjectRoot "tools\blueprint\$($family[1])"),
            '--project-root', $ProjectRoot,
            '--graph', $spec[0]
        )
        if ($spec[1]) { $arguments += '--paste' }
        & python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Cinematic pose $($family[0]) contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
        }
    }
}

$flightProfileNonce = [guid]::NewGuid().ToString('N')
$flightProfileRoot = Join-Path $scratchRoot "edd-flight-profile-$flightProfileNonce"
$flightProfileReset = Join-Path $flightProfileRoot 'reset-flight-profile-state-v1.eddgraph'
$flightProfileResetPaste = Join-Path $flightProfileRoot 'reset-flight-profile-state-v1-paste.eddgraph'
$flightProfileResetRepeat = Join-Path $flightProfileRoot 'reset-flight-profile-state-v1-repeat.eddgraph'
$flightProfileResetRepeatPaste = Join-Path $flightProfileRoot 'reset-flight-profile-state-v1-repeat-paste.eddgraph'
$flightProfileValidation = Join-Path $flightProfileRoot 'validate-flight-profile-inputs-v1.eddgraph'
$flightProfileValidationPaste = Join-Path $flightProfileRoot 'validate-flight-profile-inputs-v1-paste.eddgraph'
$flightProfileValidationRepeat = Join-Path $flightProfileRoot 'validate-flight-profile-inputs-v1-repeat.eddgraph'
$flightProfileValidationRepeatPaste = Join-Path $flightProfileRoot 'validate-flight-profile-inputs-v1-repeat-paste.eddgraph'
$flightProfileResolver = Join-Path $flightProfileRoot 'resolve-flight-profile-preset-v1.eddgraph'
$flightProfileResolverPaste = Join-Path $flightProfileRoot 'resolve-flight-profile-preset-v1-paste.eddgraph'
$flightProfileResolverRepeat = Join-Path $flightProfileRoot 'resolve-flight-profile-preset-v1-repeat.eddgraph'
$flightProfileResolverRepeatPaste = Join-Path $flightProfileRoot 'resolve-flight-profile-preset-v1-repeat-paste.eddgraph'
$flightProfileCandidates = Join-Path $flightProfileRoot 'build-flight-profile-candidates-v1.eddgraph'
$flightProfileCandidatesPaste = Join-Path $flightProfileRoot 'build-flight-profile-candidates-v1-paste.eddgraph'
$flightProfileCandidatesRepeat = Join-Path $flightProfileRoot 'build-flight-profile-candidates-v1-repeat.eddgraph'
$flightProfileCandidatesRepeatPaste = Join-Path $flightProfileRoot 'build-flight-profile-candidates-v1-repeat-paste.eddgraph'
$flightProfileCommit = Join-Path $flightProfileRoot 'commit-compiled-flight-profiles-v1.eddgraph'
$flightProfileCommitPaste = Join-Path $flightProfileRoot 'commit-compiled-flight-profiles-v1-paste.eddgraph'
$flightProfileCommitRepeat = Join-Path $flightProfileRoot 'commit-compiled-flight-profiles-v1-repeat.eddgraph'
$flightProfileCommitRepeatPaste = Join-Path $flightProfileRoot 'commit-compiled-flight-profiles-v1-repeat-paste.eddgraph'
$flightProfileCompile = Join-Path $flightProfileRoot 'compile-flight-profiles-v1.eddgraph'
$flightProfileCompilePaste = Join-Path $flightProfileRoot 'compile-flight-profiles-v1-paste.eddgraph'
$flightProfileCompileRepeat = Join-Path $flightProfileRoot 'compile-flight-profiles-v1-repeat.eddgraph'
$flightProfileCompileRepeatPaste = Join-Path $flightProfileRoot 'compile-flight-profiles-v1-repeat-paste.eddgraph'
$flightProfileEvaluator = Join-Path $flightProfileRoot 'evaluate-compiled-flight-profile-v1.eddgraph'
$flightProfileEvaluatorPaste = Join-Path $flightProfileRoot 'evaluate-compiled-flight-profile-v1-paste.eddgraph'
$flightProfileEvaluatorRepeat = Join-Path $flightProfileRoot 'evaluate-compiled-flight-profile-v1-repeat.eddgraph'
$flightProfileEvaluatorRepeatPaste = Join-Path $flightProfileRoot 'evaluate-compiled-flight-profile-v1-repeat-paste.eddgraph'
foreach ($spec in @(
    @('Build-FlightProfileResetGraph.py', $flightProfileReset, $flightProfileResetPaste, $flightProfileResetRepeat, $flightProfileResetRepeatPaste),
    @('Build-FlightProfileValidationGraph.py', $flightProfileValidation, $flightProfileValidationPaste, $flightProfileValidationRepeat, $flightProfileValidationRepeatPaste),
    @('Build-FlightProfileResolverGraph.py', $flightProfileResolver, $flightProfileResolverPaste, $flightProfileResolverRepeat, $flightProfileResolverRepeatPaste),
    @('Build-FlightProfileCandidatesGraph.py', $flightProfileCandidates, $flightProfileCandidatesPaste, $flightProfileCandidatesRepeat, $flightProfileCandidatesRepeatPaste),
    @('Build-FlightProfileCommitGraph.py', $flightProfileCommit, $flightProfileCommitPaste, $flightProfileCommitRepeat, $flightProfileCommitRepeatPaste),
    @('Build-FlightProfileCompileGraph.py', $flightProfileCompile, $flightProfileCompilePaste, $flightProfileCompileRepeat, $flightProfileCompileRepeatPaste),
    @('Build-FlightProfileEvaluatorGraph.py', $flightProfileEvaluator, $flightProfileEvaluatorPaste, $flightProfileEvaluatorRepeat, $flightProfileEvaluatorRepeatPaste)
)) {
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec[0])") `
        --project-root $ProjectRoot --output $spec[1] --paste-output $spec[2]
    if ($LASTEXITCODE -ne 0) { throw "Flight-profile graph generation failed: $($spec[0])" }
    & python (Join-Path $ProjectRoot "tools\blueprint\$($spec[0])") `
        --project-root $ProjectRoot --output $spec[3] --paste-output $spec[4]
    if ($LASTEXITCODE -ne 0) { throw "Repeated flight-profile graph generation failed: $($spec[0])" }
}
foreach ($pair in @(
    @($flightProfileReset, $flightProfileResetRepeat),
    @($flightProfileResetPaste, $flightProfileResetRepeatPaste),
    @($flightProfileValidation, $flightProfileValidationRepeat),
    @($flightProfileValidationPaste, $flightProfileValidationRepeatPaste),
    @($flightProfileResolver, $flightProfileResolverRepeat),
    @($flightProfileResolverPaste, $flightProfileResolverRepeatPaste),
    @($flightProfileCandidates, $flightProfileCandidatesRepeat),
    @($flightProfileCandidatesPaste, $flightProfileCandidatesRepeatPaste),
    @($flightProfileCommit, $flightProfileCommitRepeat),
    @($flightProfileCommitPaste, $flightProfileCommitRepeatPaste),
    @($flightProfileCompile, $flightProfileCompileRepeat),
    @($flightProfileCompilePaste, $flightProfileCompileRepeatPaste),
    @($flightProfileEvaluator, $flightProfileEvaluatorRepeat),
    @($flightProfileEvaluatorPaste, $flightProfileEvaluatorRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Flight-profile graph generation is not deterministic: $($pair[0])"
    }
}
foreach ($family in @(
    @('Reset', 'Test-FlightProfileResetContracts.py', $flightProfileReset, $flightProfileResetPaste, 'reset-flight-profile-state-v1'),
    @('Validation', 'Test-FlightProfileValidationContracts.py', $flightProfileValidation, $flightProfileValidationPaste, 'validate-flight-profile-inputs-v1'),
    @('Resolver', 'Test-FlightProfileResolverContracts.py', $flightProfileResolver, $flightProfileResolverPaste, 'resolve-flight-profile-preset-v1'),
    @('Candidates', 'Test-FlightProfileCandidatesContracts.py', $flightProfileCandidates, $flightProfileCandidatesPaste, 'build-flight-profile-candidates-v1'),
    @('Commit', 'Test-FlightProfileCommitContracts.py', $flightProfileCommit, $flightProfileCommitPaste, 'commit-compiled-flight-profiles-v1'),
    @('Compile', 'Test-FlightProfileCompileContracts.py', $flightProfileCompile, $flightProfileCompilePaste, 'compile-flight-profiles-v1'),
    @('Evaluator', 'Test-FlightProfileEvaluatorContracts.py', $flightProfileEvaluator, $flightProfileEvaluatorPaste, 'evaluate-compiled-flight-profile-v1')
)) {
    foreach ($spec in @(
        @($family[2], $false),
        @($family[3], $true),
        @((Join-Path $ProjectRoot "tools\blueprint\snippets\$($family[4]).eddgraph"), $false),
        @((Join-Path $ProjectRoot "tools\blueprint\snippets\$($family[4])-paste.eddgraph"), $true),
        @((Join-Path $ProjectRoot "tools\blueprint\live-snippets\$($family[4]).eddgraph"), $false)
    )) {
        & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
        $arguments = @(
            (Join-Path $ProjectRoot "tools\blueprint\$($family[1])"),
            '--project-root', $ProjectRoot,
            '--graph', $spec[0]
        )
        if ($spec[1]) { $arguments += '--paste' }
        & python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Flight-profile $($family[0]) contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
        }
    }
}

$smoothedProfileNonce = [guid]::NewGuid().ToString('N')
$smoothedProfileRoot = Join-Path $scratchRoot "edd-smoothed-flight-profile-$smoothedProfileNonce"
$smoothedProfileReset = Join-Path $smoothedProfileRoot 'reset-smoothed-flight-profile-v1.eddgraph'
$smoothedProfileResetPaste = Join-Path $smoothedProfileRoot 'reset-smoothed-flight-profile-v1-paste.eddgraph'
$smoothedProfileResetRepeat = Join-Path $smoothedProfileRoot 'reset-smoothed-flight-profile-v1-repeat.eddgraph'
$smoothedProfileResetRepeatPaste = Join-Path $smoothedProfileRoot 'reset-smoothed-flight-profile-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileResetGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileReset --paste-output $smoothedProfileResetPaste
if ($LASTEXITCODE -ne 0) { throw "Smoothed flight-profile reset generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileResetGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileResetRepeat --paste-output $smoothedProfileResetRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated smoothed flight-profile reset generation failed with exit code $LASTEXITCODE." }
foreach ($pair in @(
    @($smoothedProfileReset, $smoothedProfileResetRepeat),
    @($smoothedProfileResetPaste, $smoothedProfileResetRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Smoothed flight-profile reset generation is not deterministic: $($pair[0])"
    }
}
foreach ($spec in @(
    @($smoothedProfileReset, $false),
    @($smoothedProfileResetPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-smoothed-flight-profile-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\reset-smoothed-flight-profile-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\reset-smoothed-flight-profile-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-SmoothedFlightProfileResetContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Smoothed flight-profile reset contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}

$smoothedProfileStage = Join-Path $smoothedProfileRoot 'stage-smoothed-flight-profile-samples-v1.eddgraph'
$smoothedProfileStagePaste = Join-Path $smoothedProfileRoot 'stage-smoothed-flight-profile-samples-v1-paste.eddgraph'
$smoothedProfileStageRepeat = Join-Path $smoothedProfileRoot 'stage-smoothed-flight-profile-samples-v1-repeat.eddgraph'
$smoothedProfileStageRepeatPaste = Join-Path $smoothedProfileRoot 'stage-smoothed-flight-profile-samples-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileStageGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileStage --paste-output $smoothedProfileStagePaste
if ($LASTEXITCODE -ne 0) { throw "Smoothed flight-profile stage generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileStageGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileStageRepeat --paste-output $smoothedProfileStageRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated smoothed flight-profile stage generation failed with exit code $LASTEXITCODE." }
foreach ($pair in @(
    @($smoothedProfileStage, $smoothedProfileStageRepeat),
    @($smoothedProfileStagePaste, $smoothedProfileStageRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Smoothed flight-profile stage generation is not deterministic: $($pair[0])"
    }
}
foreach ($spec in @(
    @($smoothedProfileStage, $false),
    @($smoothedProfileStagePaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-smoothed-flight-profile-samples-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\stage-smoothed-flight-profile-samples-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\stage-smoothed-flight-profile-samples-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-SmoothedFlightProfileStageContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Smoothed flight-profile stage contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}

$smoothedProfilePublish = Join-Path $smoothedProfileRoot 'publish-smoothed-flight-profile-v1.eddgraph'
$smoothedProfilePublishPaste = Join-Path $smoothedProfileRoot 'publish-smoothed-flight-profile-v1-paste.eddgraph'
$smoothedProfilePublishRepeat = Join-Path $smoothedProfileRoot 'publish-smoothed-flight-profile-v1-repeat.eddgraph'
$smoothedProfilePublishRepeatPaste = Join-Path $smoothedProfileRoot 'publish-smoothed-flight-profile-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfilePublishGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfilePublish --paste-output $smoothedProfilePublishPaste
if ($LASTEXITCODE -ne 0) { throw "Smoothed flight-profile publish generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfilePublishGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfilePublishRepeat --paste-output $smoothedProfilePublishRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated smoothed flight-profile publish generation failed with exit code $LASTEXITCODE." }
foreach ($pair in @(
    @($smoothedProfilePublish, $smoothedProfilePublishRepeat),
    @($smoothedProfilePublishPaste, $smoothedProfilePublishRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Smoothed flight-profile publish generation is not deterministic: $($pair[0])"
    }
}
foreach ($spec in @(
    @($smoothedProfilePublish, $false),
    @($smoothedProfilePublishPaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\publish-smoothed-flight-profile-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\publish-smoothed-flight-profile-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\publish-smoothed-flight-profile-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-SmoothedFlightProfilePublishContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Smoothed flight-profile publish contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}

$smoothedProfileEvaluate = Join-Path $smoothedProfileRoot 'evaluate-smoothed-flight-profile-v1.eddgraph'
$smoothedProfileEvaluatePaste = Join-Path $smoothedProfileRoot 'evaluate-smoothed-flight-profile-v1-paste.eddgraph'
$smoothedProfileEvaluateRepeat = Join-Path $smoothedProfileRoot 'evaluate-smoothed-flight-profile-v1-repeat.eddgraph'
$smoothedProfileEvaluateRepeatPaste = Join-Path $smoothedProfileRoot 'evaluate-smoothed-flight-profile-v1-repeat-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileEvaluateGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileEvaluate --paste-output $smoothedProfileEvaluatePaste
if ($LASTEXITCODE -ne 0) { throw "Smoothed flight-profile evaluate generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-SmoothedFlightProfileEvaluateGraph.py') `
    --project-root $ProjectRoot --output $smoothedProfileEvaluateRepeat --paste-output $smoothedProfileEvaluateRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated smoothed flight-profile evaluate generation failed with exit code $LASTEXITCODE." }
foreach ($pair in @(
    @($smoothedProfileEvaluate, $smoothedProfileEvaluateRepeat),
    @($smoothedProfileEvaluatePaste, $smoothedProfileEvaluateRepeatPaste)
)) {
    if ((Get-FileHash -Algorithm SHA256 $pair[0]).Hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash) {
        throw "Smoothed flight-profile evaluate generation is not deterministic: $($pair[0])"
    }
}
foreach ($spec in @(
    @($smoothedProfileEvaluate, $false),
    @($smoothedProfileEvaluatePaste, $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-smoothed-flight-profile-v1.eddgraph'), $false),
    @((Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-smoothed-flight-profile-v1-paste.eddgraph'), $true),
    @((Join-Path $ProjectRoot 'tools\blueprint\live-snippets\evaluate-smoothed-flight-profile-v1.eddgraph'), $false)
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $spec[0]
    $arguments = @(
        (Join-Path $ProjectRoot 'tools\blueprint\Test-SmoothedFlightProfileEvaluateContracts.py'),
        '--project-root', $ProjectRoot,
        '--graph', $spec[0]
    )
    if ($spec[1]) { $arguments += '--paste' }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Smoothed flight-profile evaluate contracts failed with exit code ${LASTEXITCODE}: $($spec[0])"
    }
}

$trajectoryScalarNonce = [guid]::NewGuid().ToString('N')
$trajectoryScalarRoot = Join-Path $scratchRoot "edd-trajectory-scalar-$trajectoryScalarNonce"
$trajectoryScalarFull = Join-Path $trajectoryScalarRoot 'full'
$trajectoryScalarPaste = Join-Path $trajectoryScalarRoot 'paste'
$trajectoryScalarRepeat = Join-Path $trajectoryScalarRoot 'repeat'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryScalarEvaluatorGraphs.py') `
    --project-root $ProjectRoot --output-dir $trajectoryScalarFull --paste-dir $trajectoryScalarPaste
if ($LASTEXITCODE -ne 0) {
    throw "Trajectory scalar graph generation failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryScalarEvaluatorGraphs.py') `
    --project-root $ProjectRoot --output-dir $trajectoryScalarRepeat
if ($LASTEXITCODE -ne 0) {
    throw "Repeated trajectory scalar graph generation failed with exit code $LASTEXITCODE."
}
foreach ($name in @('evaluate-time-profile-v1.eddgraph', 'evaluate-quintic-scalar-v1.eddgraph')) {
    $generated = Join-Path $trajectoryScalarFull $name
    $repeated = Join-Path $trajectoryScalarRepeat $name
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$name"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $repeated).Hash) {
        throw "$name generation is not deterministic."
    }
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "$name has drifted from its deterministic generator."
    }
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $generated
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path (Join-Path $trajectoryScalarPaste $name)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryScalarEvaluatorContracts.py') `
    --project-root $ProjectRoot --input-dir $trajectoryScalarFull
if ($LASTEXITCODE -ne 0) {
    throw "Trajectory scalar full-graph contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryScalarEvaluatorContracts.py') `
    --project-root $ProjectRoot --input-dir $trajectoryScalarPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Trajectory scalar paste-graph contracts failed with exit code $LASTEXITCODE."
}

$trajectoryVectorRoot = Join-Path $scratchRoot "edd-trajectory-vector-$trajectoryScalarNonce"
$trajectoryVectorFull = Join-Path $trajectoryVectorRoot 'evaluate-quintic-vector-v1.eddgraph'
$trajectoryVectorPaste = Join-Path $trajectoryVectorRoot 'evaluate-quintic-vector-v1-paste.eddgraph'
$trajectoryVectorRepeat = Join-Path $trajectoryVectorRoot 'evaluate-quintic-vector-v1-repeat.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryVectorEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $trajectoryVectorFull --paste-output $trajectoryVectorPaste
if ($LASTEXITCODE -ne 0) { throw "Trajectory vector graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryVectorEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $trajectoryVectorRepeat
if ($LASTEXITCODE -ne 0) { throw "Repeated trajectory vector graph generation failed with exit code $LASTEXITCODE." }
$trajectoryVectorChecked = Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-quintic-vector-v1.eddgraph'
foreach ($comparison in @($trajectoryVectorRepeat, $trajectoryVectorChecked)) {
    if ((Get-FileHash -Algorithm SHA256 $trajectoryVectorFull).Hash -ne (Get-FileHash -Algorithm SHA256 $comparison).Hash) {
        throw "Trajectory vector graph is not deterministic or has drifted."
    }
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $trajectoryVectorFull
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $trajectoryVectorPaste
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryVectorEvaluatorContracts.py') `
    --project-root $ProjectRoot --vector-path $trajectoryVectorFull
if ($LASTEXITCODE -ne 0) { throw "Trajectory vector full-graph contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryVectorEvaluatorContracts.py') `
    --project-root $ProjectRoot --vector-path $trajectoryVectorPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Trajectory vector paste-graph contracts failed with exit code $LASTEXITCODE." }
$trajectoryVectorLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\evaluate-quintic-vector-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $trajectoryVectorLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryVectorEvaluatorContracts.py') `
    --project-root $ProjectRoot --vector-path $trajectoryVectorLive
if ($LASTEXITCODE -ne 0) { throw "Trajectory vector live-graph contracts failed with exit code $LASTEXITCODE." }

$trajectoryQuaternionNonce = [guid]::NewGuid().ToString('N')
$trajectoryQuaternionRoot = Join-Path $scratchRoot "edd-trajectory-quaternion-$trajectoryQuaternionNonce"
$trajectoryQuaternionFull = Join-Path $trajectoryQuaternionRoot 'evaluate-spherical-bezier-quaternion-v1.eddgraph'
$trajectoryQuaternionPaste = Join-Path $trajectoryQuaternionRoot 'evaluate-spherical-bezier-quaternion-v1-paste.eddgraph'
$trajectoryQuaternionRepeat = Join-Path $trajectoryQuaternionRoot 'evaluate-spherical-bezier-quaternion-v1-repeat.eddgraph'
$trajectoryQuaternionRepeatPaste = Join-Path $trajectoryQuaternionRoot 'evaluate-spherical-bezier-quaternion-v1-repeat-paste.eddgraph'
New-Item -ItemType Directory -Path $trajectoryQuaternionRoot -Force | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryQuaternionEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $trajectoryQuaternionFull --paste-output $trajectoryQuaternionPaste
if ($LASTEXITCODE -ne 0) { throw "Trajectory quaternion graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-TrajectoryQuaternionEvaluatorGraph.py') `
    --project-root $ProjectRoot --output $trajectoryQuaternionRepeat --paste-output $trajectoryQuaternionRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated trajectory quaternion graph generation failed with exit code $LASTEXITCODE." }
foreach ($comparison in @(
    @($trajectoryQuaternionFull, $trajectoryQuaternionRepeat, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-spherical-bezier-quaternion-v1.eddgraph')),
    @($trajectoryQuaternionPaste, $trajectoryQuaternionRepeatPaste, (Join-Path $ProjectRoot 'tools\blueprint\snippets\evaluate-spherical-bezier-quaternion-v1-paste.eddgraph'))
)) {
    $generated, $repeated, $checked = $comparison
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $repeated).Hash) {
        throw "Trajectory quaternion graph generation is not deterministic: $generated"
    }
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Trajectory quaternion checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryQuaternionNativeNodeForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\trajectory-quaternion-native-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) { throw "Trajectory quaternion native node-form contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryQuaternionEvaluatorContracts.py') `
    --project-root $ProjectRoot --graph $trajectoryQuaternionFull
if ($LASTEXITCODE -ne 0) { throw "Trajectory quaternion full-graph contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryQuaternionEvaluatorContracts.py') `
    --project-root $ProjectRoot --graph $trajectoryQuaternionPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Trajectory quaternion paste-graph contracts failed with exit code $LASTEXITCODE." }
$trajectoryQuaternionLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\evaluate-spherical-bezier-quaternion-v1.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-TrajectoryQuaternionEvaluatorContracts.py') `
    --project-root $ProjectRoot --graph $trajectoryQuaternionLive
if ($LASTEXITCODE -ne 0) { throw "Trajectory quaternion live-graph contracts failed with exit code $LASTEXITCODE." }

$orientationCompilerNonce = [guid]::NewGuid().ToString('N')
$orientationCompilerRoot = Join-Path $scratchRoot "edd-orientation-compiler-$orientationCompilerNonce"
$orientationCompilerNative = Join-Path $orientationCompilerRoot 'native-node-forms.eddgraph'
$orientationCompilerFull = Join-Path $orientationCompilerRoot 'full'
$orientationCompilerPaste = Join-Path $orientationCompilerRoot 'paste'
$orientationCompilerRepeatFull = Join-Path $orientationCompilerRoot 'repeat-full'
$orientationCompilerRepeatPaste = Join-Path $orientationCompilerRoot 'repeat-paste'
foreach ($path in @($orientationCompilerFull, $orientationCompilerPaste, $orientationCompilerRepeatFull, $orientationCompilerRepeatPaste)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationCompilerNativeNodeForms.py') `
    --project-root $ProjectRoot --output $orientationCompilerNative
if ($LASTEXITCODE -ne 0) { throw "Orientation compiler native-node generation failed with exit code $LASTEXITCODE." }
$orientationCompilerNativeChecked = Join-Path $ProjectRoot 'tools\blueprint\templates\orientation-compiler-native-node-forms.eddgraph'
if ((Get-FileHash -Algorithm SHA256 $orientationCompilerNative).Hash -ne (Get-FileHash -Algorithm SHA256 $orientationCompilerNativeChecked).Hash) {
    throw "Orientation compiler checked-in native-node forms have drifted: $orientationCompilerNativeChecked"
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationCompilerGraphs.py') `
    --project-root $ProjectRoot --output-dir $orientationCompilerFull --paste-dir $orientationCompilerPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation compiler graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationCompilerGraphs.py') `
    --project-root $ProjectRoot --output-dir $orientationCompilerRepeatFull --paste-dir $orientationCompilerRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated orientation compiler graph generation failed with exit code $LASTEXITCODE." }
$orientationCompilerStems = @(
    'compute-orientation-log-delta-v1',
    'compute-orientation-tangent-rate-v1',
    'build-orientation-segment-controls-v1'
)
foreach ($stem in $orientationCompilerStems) {
    foreach ($suffix in @('.eddgraph', '-paste.eddgraph')) {
        $generatedRoot = if ($suffix -eq '.eddgraph') { $orientationCompilerFull } else { $orientationCompilerPaste }
        $repeatRoot = if ($suffix -eq '.eddgraph') { $orientationCompilerRepeatFull } else { $orientationCompilerRepeatPaste }
        $generated = Join-Path $generatedRoot "$stem$suffix"
        $repeated = Join-Path $repeatRoot "$stem$suffix"
        $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$stem$suffix"
        if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $repeated).Hash) {
            throw "Orientation compiler graph generation is not deterministic: $generated"
        }
        if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
            throw "Orientation compiler checked-in graph has drifted: $checked"
        }
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationCompilerContracts.py') `
    --project-root $ProjectRoot --input-dir $orientationCompilerFull
if ($LASTEXITCODE -ne 0) { throw "Orientation compiler full-graph contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationCompilerContracts.py') `
    --project-root $ProjectRoot --input-dir $orientationCompilerPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation compiler paste-graph contracts failed with exit code $LASTEXITCODE." }
$orientationCompilerLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationCompilerContracts.py') `
    --project-root $ProjectRoot --input-dir $orientationCompilerLive
if ($LASTEXITCODE -ne 0) { throw "Orientation compiler exact post-compile contracts failed with exit code $LASTEXITCODE." }

$orientationResetFull = Join-Path $orientationCompilerRoot 'reset-orientation-track-candidate-v1.eddgraph'
$orientationResetPaste = Join-Path $orientationCompilerRoot 'reset-orientation-track-candidate-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackResetGraph.py') `
    --project-root $ProjectRoot --output $orientationResetFull --paste-output $orientationResetPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track reset graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationResetFull, $orientationResetPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track reset checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackResetContracts.py') `
    --project-root $ProjectRoot --graph $orientationResetFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track reset full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackResetContracts.py') `
    --project-root $ProjectRoot --graph $orientationResetPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track reset paste contracts failed with exit code $LASTEXITCODE." }

$orientationValidationFull = Join-Path $orientationCompilerRoot 'validate-orientation-track-inputs-v1.eddgraph'
$orientationValidationPaste = Join-Path $orientationCompilerRoot 'validate-orientation-track-inputs-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackValidationGraph.py') `
    --project-root $ProjectRoot --output $orientationValidationFull --paste-output $orientationValidationPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track validation graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationValidationFull, $orientationValidationPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track validation checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackValidationContracts.py') `
    --project-root $ProjectRoot --graph $orientationValidationFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track validation full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackValidationContracts.py') `
    --project-root $ProjectRoot --graph $orientationValidationPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track validation paste contracts failed with exit code $LASTEXITCODE." }

$orientationAlignmentFull = Join-Path $orientationCompilerRoot 'align-orientation-waypoints-v1.eddgraph'
$orientationAlignmentPaste = Join-Path $orientationCompilerRoot 'align-orientation-waypoints-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackAlignmentGraph.py') `
    --project-root $ProjectRoot --output $orientationAlignmentFull --paste-output $orientationAlignmentPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track alignment graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationAlignmentFull, $orientationAlignmentPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track alignment checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackAlignmentContracts.py') `
    --project-root $ProjectRoot --graph $orientationAlignmentFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track alignment full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackAlignmentContracts.py') `
    --project-root $ProjectRoot --graph $orientationAlignmentPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track alignment paste contracts failed with exit code $LASTEXITCODE." }

$orientationDeltaFull = Join-Path $orientationCompilerRoot 'compute-orientation-forward-deltas-v1.eddgraph'
$orientationDeltaPaste = Join-Path $orientationCompilerRoot 'compute-orientation-forward-deltas-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationForwardDeltasGraph.py') `
    --project-root $ProjectRoot --output $orientationDeltaFull --paste-output $orientationDeltaPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation forward-delta graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationDeltaFull, $orientationDeltaPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation forward-delta checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationForwardDeltasContracts.py') `
    --project-root $ProjectRoot --graph $orientationDeltaFull
if ($LASTEXITCODE -ne 0) { throw "Orientation forward-delta full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationForwardDeltasContracts.py') `
    --project-root $ProjectRoot --graph $orientationDeltaPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation forward-delta paste contracts failed with exit code $LASTEXITCODE." }

$orientationTangentFull = Join-Path $orientationCompilerRoot 'compute-orientation-track-tangent-rates-v1.eddgraph'
$orientationTangentPaste = Join-Path $orientationCompilerRoot 'compute-orientation-track-tangent-rates-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackTangentRatesGraph.py') `
    --project-root $ProjectRoot --output $orientationTangentFull --paste-output $orientationTangentPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track tangent-rate graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationTangentFull, $orientationTangentPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track tangent-rate checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackTangentRatesContracts.py') `
    --project-root $ProjectRoot --graph $orientationTangentFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track tangent-rate full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackTangentRatesContracts.py') `
    --project-root $ProjectRoot --graph $orientationTangentPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track tangent-rate paste contracts failed with exit code $LASTEXITCODE." }

$orientationSegmentsFull = Join-Path $orientationCompilerRoot 'build-orientation-track-segments-v1.eddgraph'
$orientationSegmentsPaste = Join-Path $orientationCompilerRoot 'build-orientation-track-segments-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackSegmentsGraph.py') `
    --project-root $ProjectRoot --output $orientationSegmentsFull --paste-output $orientationSegmentsPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track segment graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationSegmentsFull, $orientationSegmentsPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track segment checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackSegmentsContracts.py') `
    --project-root $ProjectRoot --graph $orientationSegmentsFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track segment full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackSegmentsContracts.py') `
    --project-root $ProjectRoot --graph $orientationSegmentsPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track segment paste contracts failed with exit code $LASTEXITCODE." }

$orientationCommitFull = Join-Path $orientationCompilerRoot 'commit-compiled-orientation-track-v1.eddgraph'
$orientationCommitPaste = Join-Path $orientationCompilerRoot 'commit-compiled-orientation-track-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackCommitGraph.py') `
    --project-root $ProjectRoot --output $orientationCommitFull --paste-output $orientationCommitPaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track commit graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationCommitFull, $orientationCommitPaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track commit checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackCommitContracts.py') `
    --project-root $ProjectRoot --graph $orientationCommitFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track commit full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackCommitContracts.py') `
    --project-root $ProjectRoot --graph $orientationCommitPaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track commit paste contracts failed with exit code $LASTEXITCODE." }

$orientationCompileFull = Join-Path $orientationCompilerRoot 'compile-orientation-track-v1.eddgraph'
$orientationCompilePaste = Join-Path $orientationCompilerRoot 'compile-orientation-track-v1-paste.eddgraph'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-OrientationTrackCompileGraph.py') `
    --project-root $ProjectRoot --output $orientationCompileFull --paste-output $orientationCompilePaste
if ($LASTEXITCODE -ne 0) { throw "Orientation track compile graph generation failed with exit code $LASTEXITCODE." }
foreach ($generated in @($orientationCompileFull, $orientationCompilePaste)) {
    $checked = Join-Path $ProjectRoot "tools\blueprint\snippets\$([IO.Path]::GetFileName($generated))"
    if ((Get-FileHash -Algorithm SHA256 $generated).Hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Orientation track compile checked-in graph has drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackCompileContracts.py') `
    --project-root $ProjectRoot --graph $orientationCompileFull
if ($LASTEXITCODE -ne 0) { throw "Orientation track compile full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackCompileContracts.py') `
    --project-root $ProjectRoot --graph $orientationCompilePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Orientation track compile paste contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-OrientationTrackCompileContracts.py') `
    --project-root $ProjectRoot --graph (Join-Path $ProjectRoot 'tools\blueprint\live-snippets\compile-orientation-track-v1.eddgraph')
if ($LASTEXITCODE -ne 0) { throw "Orientation track compile exact post-compile contracts failed with exit code $LASTEXITCODE." }

$arcTableRoot = Join-Path $scratchRoot "edd-arc-table-$orientationCompilerNonce"
$arcTableFull = Join-Path $arcTableRoot 'invert-arc-length-table-v1.eddgraph'
$arcTablePaste = Join-Path $arcTableRoot 'invert-arc-length-table-v1-paste.eddgraph'
$arcTableRepeat = Join-Path $arcTableRoot 'invert-arc-length-table-v1-repeat.eddgraph'
$arcTableRepeatPaste = Join-Path $arcTableRoot 'invert-arc-length-table-v1-repeat-paste.eddgraph'
New-Item -ItemType Directory -Path $arcTableRoot -Force | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-ArcTableInversionGraph.py') `
    --project-root $ProjectRoot --output $arcTableFull --paste-output $arcTablePaste
if ($LASTEXITCODE -ne 0) { throw "Arc-table inversion graph generation failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-ArcTableInversionGraph.py') `
    --project-root $ProjectRoot --output $arcTableRepeat --paste-output $arcTableRepeatPaste
if ($LASTEXITCODE -ne 0) { throw "Repeated arc-table inversion graph generation failed with exit code $LASTEXITCODE." }
foreach ($pair in @(
    @($arcTableFull, $arcTableRepeat, 'tools\blueprint\snippets\invert-arc-length-table-v1.eddgraph'),
    @($arcTablePaste, $arcTableRepeatPaste, 'tools\blueprint\snippets\invert-arc-length-table-v1-paste.eddgraph')
)) {
    $checked = Join-Path $ProjectRoot $pair[2]
    $hash = (Get-FileHash -Algorithm SHA256 $pair[0]).Hash
    if ($hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash -or
        $hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
        throw "Arc-table inversion graph is nondeterministic or drifted: $checked"
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-ArcTableInversionContracts.py') `
    --project-root $ProjectRoot --graph $arcTableFull
if ($LASTEXITCODE -ne 0) { throw "Arc-table inversion full contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-ArcTableInversionContracts.py') `
    --project-root $ProjectRoot --graph $arcTablePaste --paste
if ($LASTEXITCODE -ne 0) { throw "Arc-table inversion paste contracts failed with exit code $LASTEXITCODE." }
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-ArcTableInversionContracts.py') `
    --project-root $ProjectRoot --graph (Join-Path $ProjectRoot 'tools\blueprint\live-snippets\invert-arc-length-table-v1.eddgraph')
if ($LASTEXITCODE -ne 0) { throw "Arc-table inversion exact post-compile contracts failed with exit code $LASTEXITCODE." }

$adaptiveArcRoot = Join-Path $scratchRoot "edd-adaptive-arc-$orientationCompilerNonce"
New-Item -ItemType Directory -Path $adaptiveArcRoot -Force | Out-Null
foreach ($spec in @(
    @('Build-AdaptiveArcResetGraph.py', 'Test-AdaptiveArcResetContracts.py', 'reset-adaptive-arc-build-v1'),
    @('Build-AdaptiveArcValidationGraph.py', 'Test-AdaptiveArcValidationContracts.py', 'validate-adaptive-arc-build-inputs-v1'),
    @('Build-AdaptiveArcInitializationGraph.py', 'Test-AdaptiveArcInitializationContracts.py', 'initialize-adaptive-arc-build-v1'),
    @('Build-AdaptiveArcProcessGraph.py', 'Test-AdaptiveArcProcessContracts.py', 'process-adaptive-arc-build-v1'),
    @('Build-AdaptiveArcCommitGraph.py', 'Test-AdaptiveArcCommitContracts.py', 'commit-adaptive-arc-build-v1'),
    @('Build-AdaptiveArcCompileGraph.py', 'Test-AdaptiveArcCompileContracts.py', 'build-adaptive-arc-table-v1')
)) {
    $builder = Join-Path $ProjectRoot "tools\blueprint\$($spec[0])"
    $contract = Join-Path $ProjectRoot "tools\blueprint\$($spec[1])"
    $stem = $spec[2]
    $full = Join-Path $adaptiveArcRoot "$stem.eddgraph"
    $paste = Join-Path $adaptiveArcRoot "$stem-paste.eddgraph"
    $repeat = Join-Path $adaptiveArcRoot "$stem-repeat.eddgraph"
    $repeatPaste = Join-Path $adaptiveArcRoot "$stem-repeat-paste.eddgraph"
    & python $builder --project-root $ProjectRoot --output $full --paste-output $paste
    if ($LASTEXITCODE -ne 0) { throw "Adaptive arc graph generation failed for $stem with exit code $LASTEXITCODE." }
    & python $builder --project-root $ProjectRoot --output $repeat --paste-output $repeatPaste
    if ($LASTEXITCODE -ne 0) { throw "Repeated adaptive arc graph generation failed for $stem with exit code $LASTEXITCODE." }
    foreach ($pair in @(
        @($full, $repeat, "tools\blueprint\snippets\$stem.eddgraph"),
        @($paste, $repeatPaste, "tools\blueprint\snippets\$stem-paste.eddgraph")
    )) {
        $checked = Join-Path $ProjectRoot $pair[2]
        $hash = (Get-FileHash -Algorithm SHA256 $pair[0]).Hash
        if ($hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash -or
            $hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
            throw "Adaptive arc graph is nondeterministic or drifted: $checked"
        }
    }
    & python $contract --project-root $ProjectRoot --graph $full
    if ($LASTEXITCODE -ne 0) { throw "Adaptive arc full contracts failed for $stem with exit code $LASTEXITCODE." }
    & python $contract --project-root $ProjectRoot --graph $paste --paste
    if ($LASTEXITCODE -ne 0) { throw "Adaptive arc paste contracts failed for $stem with exit code $LASTEXITCODE." }
    & python $contract --project-root $ProjectRoot --graph (Join-Path $ProjectRoot "tools\blueprint\live-snippets\$stem.eddgraph")
    if ($LASTEXITCODE -ne 0) { throw "Adaptive arc exact post-compile contracts failed for $stem with exit code $LASTEXITCODE." }
}

$positionRouteRoot = Join-Path $scratchRoot "edd-position-route-$orientationCompilerNonce"
New-Item -ItemType Directory -Path $positionRouteRoot -Force | Out-Null
foreach ($spec in @(
    @('Build-PositionRouteResetGraph.py', 'Test-PositionRouteResetContracts.py', 'reset-position-route-candidate-v1'),
    @('Build-PositionRouteValidationGraph.py', 'Test-PositionRouteValidationContracts.py', 'validate-position-route-inputs-v1'),
    @('Build-PositionRouteVelocitiesGraph.py', 'Test-PositionRouteVelocitiesContracts.py', 'compute-position-route-velocities-v1'),
    @('Build-PositionRouteSegmentsGraph.py', 'Test-PositionRouteSegmentsContracts.py', 'build-position-route-segments-v1'),
    @('Build-PositionRouteCommitGraph.py', 'Test-PositionRouteCommitContracts.py', 'commit-compiled-position-route-v1'),
    @('Build-PositionRouteCompileGraph.py', 'Test-PositionRouteCompileContracts.py', 'compile-position-route-v1'),
    @('Build-PositionRouteArcSliceGraph.py', 'Test-PositionRouteArcSliceContracts.py', 'stage-position-route-arc-slice-v1'),
    @('Build-PositionRouteEvaluatorGraph.py', 'Test-PositionRouteEvaluatorContracts.py', 'evaluate-compiled-position-route-v1')
)) {
    $builder = Join-Path $ProjectRoot "tools\blueprint\$($spec[0])"
    $contract = Join-Path $ProjectRoot "tools\blueprint\$($spec[1])"
    $stem = $spec[2]
    $full = Join-Path $positionRouteRoot "$stem.eddgraph"
    $paste = Join-Path $positionRouteRoot "$stem-paste.eddgraph"
    $repeat = Join-Path $positionRouteRoot "$stem-repeat.eddgraph"
    $repeatPaste = Join-Path $positionRouteRoot "$stem-repeat-paste.eddgraph"
    & python $builder --project-root $ProjectRoot --output $full --paste-output $paste
    if ($LASTEXITCODE -ne 0) { throw "Position-route graph generation failed for $stem with exit code $LASTEXITCODE." }
    & python $builder --project-root $ProjectRoot --output $repeat --paste-output $repeatPaste
    if ($LASTEXITCODE -ne 0) { throw "Repeated position-route graph generation failed for $stem with exit code $LASTEXITCODE." }
    foreach ($pair in @(
        @($full, $repeat, "tools\blueprint\snippets\$stem.eddgraph"),
        @($paste, $repeatPaste, "tools\blueprint\snippets\$stem-paste.eddgraph")
    )) {
        $checked = Join-Path $ProjectRoot $pair[2]
        $hash = (Get-FileHash -Algorithm SHA256 $pair[0]).Hash
        if ($hash -ne (Get-FileHash -Algorithm SHA256 $pair[1]).Hash -or
            $hash -ne (Get-FileHash -Algorithm SHA256 $checked).Hash) {
            throw "Position-route graph is nondeterministic or drifted: $checked"
        }
    }
    & python $contract --project-root $ProjectRoot --graph $full
    if ($LASTEXITCODE -ne 0) { throw "Position-route full contracts failed for $stem with exit code $LASTEXITCODE." }
    & python $contract --project-root $ProjectRoot --graph $paste --paste
    if ($LASTEXITCODE -ne 0) { throw "Position-route paste contracts failed for $stem with exit code $LASTEXITCODE." }
    & python $contract --project-root $ProjectRoot --graph (Join-Path $ProjectRoot "tools\blueprint\live-snippets\$stem.eddgraph")
    if ($LASTEXITCODE -ne 0) { throw "Position-route exact post-compile contracts failed for $stem with exit code $LASTEXITCODE." }
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

& python (Join-Path $ProjectRoot 'tools\persistence\test_alternating_snapshot_oracle.py')
if ($LASTEXITCODE -ne 0) {
    throw "Alternating repository snapshot contracts failed with exit code $LASTEXITCODE."
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
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCodecBreakQuatNodeForm.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-codec-break-quat-node-form.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository codec BreakQuat node-form contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCodecTransformNodeForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-codec-transform-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository codec Transform node-form contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryCodecArrayNodeForms.py') `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-codec-array-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository codec Make Array node-form contracts failed with exit code $LASTEXITCODE."
}

$repositoryDecoderNativeProbe = Join-Path $scratchRoot `
    ("edd-repository-decoder-native-{0}.eddgraph" -f [guid]::NewGuid().ToString('N'))
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryDecoderNativeNodeProbe.py') `
    --project-root $ProjectRoot `
    --output $repositoryDecoderNativeProbe
if ($LASTEXITCODE -ne 0) {
    throw "Repository decoder native-node probe generation failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path $repositoryDecoderNativeProbe
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDecoderNativeNodeForms.py') `
    --project-root $ProjectRoot `
    --forms $repositoryDecoderNativeProbe
if ($LASTEXITCODE -ne 0) {
    throw "Repository decoder native-node probe contracts failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-decoder-native-node-forms.eddgraph')
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDecoderNativeNodeForms.py') `
    --project-root $ProjectRoot `
    --forms (Join-Path $ProjectRoot 'tools\blueprint\templates\repository-decoder-native-node-forms.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Accepted repository decoder native-node contracts failed with exit code $LASTEXITCODE."
}

$repositoryEncoderNonce = [guid]::NewGuid().ToString('N')
$repositoryEncoderRoot = Join-Path $scratchRoot "edd-repository-encoder-$repositoryEncoderNonce"
$repositoryEncoderFull = Join-Path $repositoryEncoderRoot 'full'
$repositoryEncoderPaste = Join-Path $repositoryEncoderRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryDocumentEncoderGraphs.py') `
    --project-root $ProjectRoot --output-dir $repositoryEncoderFull --paste-dir $repositoryEncoderPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository document encoder generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryEncoderFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryEncoderPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryEncoderFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository document encoder contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryEncoderPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository document encoder paste contracts failed with exit code $LASTEXITCODE."
}

$repositoryDecoderNonce = [guid]::NewGuid().ToString('N')
$repositoryDecoderRoot = Join-Path $scratchRoot "edd-repository-decoder-$repositoryDecoderNonce"
$repositoryDecoderFull = Join-Path $repositoryDecoderRoot 'full'
$repositoryDecoderPaste = Join-Path $repositoryDecoderRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryDocumentDecoderGraphs.py') `
    --project-root $ProjectRoot --output-dir $repositoryDecoderFull --paste-dir $repositoryDecoderPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository document decoder generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryDecoderFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryDecoderPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentDecoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryDecoderFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository document decoder contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentDecoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryDecoderPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository document decoder paste contracts failed with exit code $LASTEXITCODE."
}

$repositoryRecordEncoderNonce = [guid]::NewGuid().ToString('N')
$repositoryRecordEncoderRoot = Join-Path $scratchRoot "edd-repository-record-encoder-$repositoryRecordEncoderNonce"
$repositoryRecordEncoderFull = Join-Path $repositoryRecordEncoderRoot 'full'
$repositoryRecordEncoderPaste = Join-Path $repositoryRecordEncoderRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryRecordEncoderGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryRecordEncoderFull `
    --paste-dir $repositoryRecordEncoderPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record encoder generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecordEncoderFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecordEncoderPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordEncoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordEncoderFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository record encoder contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordEncoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordEncoderPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record encoder paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($recordEncoderName in @(
    'encode-record-published-fields-v1',
    'encode-record-source-attribution-v1',
    'encode-record-v1'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $ProjectRoot "tools\blueprint\live-snippets\$recordEncoderName.eddgraph")
    if ($LASTEXITCODE -ne 0) {
        throw "Live $recordEncoderName graph structure failed with exit code $LASTEXITCODE."
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordEncoderContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Live repository record encoder contracts failed with exit code $LASTEXITCODE."
}

$repositoryRecordDecoderNonce = [guid]::NewGuid().ToString('N')
$repositoryRecordDecoderRoot = Join-Path $scratchRoot "edd-repository-record-decoder-$repositoryRecordDecoderNonce"
$repositoryRecordDecoderFull = Join-Path $repositoryRecordDecoderRoot 'full'
$repositoryRecordDecoderPaste = Join-Path $repositoryRecordDecoderRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryRecordDecoderGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryRecordDecoderFull `
    --paste-dir $repositoryRecordDecoderPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record decoder generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecordDecoderFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecordDecoderPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordDecoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordDecoderFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository record decoder contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordDecoderContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordDecoderPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record decoder paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($recordDecoderName in @(
    'decode-record-published-fields-v1',
    'decode-record-source-attribution-v1',
    'decode-record-v1'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $ProjectRoot "tools\blueprint\live-snippets\$recordDecoderName.eddgraph")
    if ($LASTEXITCODE -ne 0) {
        throw "Live $recordDecoderName graph structure failed with exit code $LASTEXITCODE."
    }
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordDecoderContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Live repository record decoder contracts failed with exit code $LASTEXITCODE."
}
$repositoryValidationNonce = [guid]::NewGuid().ToString('N')
$repositoryValidationRoot = Join-Path $scratchRoot "edd-repository-validation-$repositoryValidationNonce"
$repositoryValidationFull = Join-Path $repositoryValidationRoot 'full'
$repositoryValidationPaste = Join-Path $repositoryValidationRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryValidationGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryValidationFull `
    --paste-dir $repositoryValidationPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository validation generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryValidationFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryValidationPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryValidationContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryValidationFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository validation contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryValidationContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryValidationPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository validation paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryValidationContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Repository validation live-round-trip contracts failed with exit code $LASTEXITCODE."
}
$repositoryPersistenceStateNonce = [guid]::NewGuid().ToString('N')
$repositoryPersistenceStateRoot = Join-Path $scratchRoot "edd-repository-persistence-state-$repositoryPersistenceStateNonce"
$repositoryPersistenceStateFull = Join-Path $repositoryPersistenceStateRoot 'full'
$repositoryPersistenceStatePaste = Join-Path $repositoryPersistenceStateRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPersistenceStateGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPersistenceStateFull `
    --paste-dir $repositoryPersistenceStatePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-state generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPersistenceStateFull -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPersistenceStatePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceStateContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryPersistenceStateFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-state contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceStateContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryPersistenceStatePaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-state paste contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceStateContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-state live-round-trip contracts failed with exit code $LASTEXITCODE."
}
$repositoryPersistenceWriterNonce = [guid]::NewGuid().ToString('N')
$repositoryPersistenceWriterRoot = Join-Path $scratchRoot "edd-repository-persistence-writer-$repositoryPersistenceWriterNonce"
$repositoryPersistenceWriterFull = Join-Path $repositoryPersistenceWriterRoot 'full'
$repositoryPersistenceWriterPaste = Join-Path $repositoryPersistenceWriterRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPersistenceWriterGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPersistenceWriterFull `
    --paste-dir $repositoryPersistenceWriterPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-writer generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPersistenceWriterFull,$repositoryPersistenceWriterPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceWriterContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryPersistenceWriterFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-writer contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceWriterContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryPersistenceWriterPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-writer paste contracts failed with exit code $LASTEXITCODE."
}
$repositoryPersistenceWriterLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
foreach ($graphName in @(
    'reset-persistence-write-v1.eddgraph',
    'build-persistence-write-storage-v1.eddgraph',
    'stage-persistence-write-v1.eddgraph',
    'commit-persistence-write-v1.eddgraph',
    'persist-repository-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $repositoryPersistenceWriterLive $graphName)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPersistenceWriterContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryPersistenceWriterLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository persistence-writer live contracts failed with exit code $LASTEXITCODE."
}
$repositorySaveGameAdapterNonce = [guid]::NewGuid().ToString('N')
$repositorySaveGameAdapterRoot = Join-Path $scratchRoot "edd-repository-savegame-adapter-$repositorySaveGameAdapterNonce"
$repositorySaveGameAdapterFull = Join-Path $repositorySaveGameAdapterRoot 'full'
$repositorySaveGameAdapterPaste = Join-Path $repositorySaveGameAdapterRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositorySaveGameAdapterGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositorySaveGameAdapterFull `
    --paste-dir $repositorySaveGameAdapterPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame adapter generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositorySaveGameAdapterFull,$repositorySaveGameAdapterPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositorySaveGameAdapterContracts.py') `
    --project-root $ProjectRoot --input-dir $repositorySaveGameAdapterFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame adapter contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositorySaveGameAdapterContracts.py') `
    --project-root $ProjectRoot --input-dir $repositorySaveGameAdapterPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame adapter paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($graphName in @(
    'read-repository-storage-slot-a-v1.eddgraph',
    'read-repository-storage-slot-b-v1.eddgraph',
    'read-repository-storage-slots-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $ProjectRoot "tools\blueprint\live-snippets\$graphName")
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositorySaveGameAdapterContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Repository SaveGame adapter live-round-trip contracts failed with exit code $LASTEXITCODE."
}
$repositoryRecoverySelectionNonce = [guid]::NewGuid().ToString('N')
$repositoryRecoverySelectionRoot = Join-Path $scratchRoot "edd-repository-recovery-selection-$repositoryRecoverySelectionNonce"
$repositoryRecoverySelectionFull = Join-Path $repositoryRecoverySelectionRoot 'full'
$repositoryRecoverySelectionPaste = Join-Path $repositoryRecoverySelectionRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryRecoverySelectionGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryRecoverySelectionFull `
    --paste-dir $repositoryRecoverySelectionPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository recovery-selection generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecoverySelectionFull,$repositoryRecoverySelectionPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecoverySelectionContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecoverySelectionFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository recovery-selection contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecoverySelectionContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecoverySelectionPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository recovery-selection paste contracts failed with exit code $LASTEXITCODE."
}
$repositoryRecoverySelectionLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
foreach ($graphName in @(
    'reset-recovery-selection-v1.eddgraph',
    'compare-recovery-string-arrays-v1.eddgraph',
    'compare-equal-generation-storage-v1.eddgraph',
    'stage-recovery-a-only-v1.eddgraph',
    'stage-recovery-b-only-v1.eddgraph',
    'stage-recovery-a-newer-v1.eddgraph',
    'stage-recovery-b-newer-v1.eddgraph',
    'select-repository-recovery-order-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $repositoryRecoverySelectionLive $graphName)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecoverySelectionContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecoverySelectionLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository recovery-selection live contracts failed with exit code $LASTEXITCODE."
}
$repositoryTombstoneRecoveryNonce = [guid]::NewGuid().ToString('N')
$repositoryTombstoneRecoveryRoot = Join-Path $scratchRoot "edd-repository-tombstone-recovery-$repositoryTombstoneRecoveryNonce"
$repositoryTombstoneRecoveryFull = Join-Path $repositoryTombstoneRecoveryRoot 'full'
$repositoryTombstoneRecoveryPaste = Join-Path $repositoryTombstoneRecoveryRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryTombstoneRecoveryGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryTombstoneRecoveryFull `
    --paste-dir $repositoryTombstoneRecoveryPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository tombstone-recovery generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryTombstoneRecoveryFull,$repositoryTombstoneRecoveryPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryTombstoneRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryTombstoneRecoveryFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository tombstone-recovery contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryTombstoneRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryTombstoneRecoveryPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository tombstone-recovery paste contracts failed with exit code $LASTEXITCODE."
}
$repositoryTombstoneRecoveryLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
foreach ($graphName in @(
    'reset-recovery-tombstones-v1.eddgraph',
    'find-recovery-string-index-v1.eddgraph',
    'validate-recovery-tombstone-channel-v1.eddgraph',
    'merge-recovery-tombstones-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $repositoryTombstoneRecoveryLive $graphName)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryTombstoneRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryTombstoneRecoveryLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository tombstone-recovery live contracts failed with exit code $LASTEXITCODE."
}
$repositoryRecordRecoveryNonce = [guid]::NewGuid().ToString('N')
$repositoryRecordRecoveryRoot = Join-Path $scratchRoot "edd-repository-record-recovery-$repositoryRecordRecoveryNonce"
$repositoryRecordRecoveryFull = Join-Path $repositoryRecordRecoveryRoot 'full'
$repositoryRecordRecoveryPaste = Join-Path $repositoryRecordRecoveryRoot 'paste'
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryRecordRecoveryGraphs.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryRecordRecoveryFull `
    --paste-dir $repositoryRecordRecoveryPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record-recovery generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryRecordRecoveryFull,$repositoryRecordRecoveryPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordRecoveryFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository record-recovery contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordRecoveryPaste --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository record-recovery paste contracts failed with exit code $LASTEXITCODE."
}
$repositoryRecordRecoveryLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets'
foreach ($graphName in @(
    'reset-recovery-records-v1.eddgraph',
    'decode-validate-recovery-envelope-v1.eddgraph',
    'scan-recovery-record-identity-v1.eddgraph',
    'append-recovery-record-if-new-v1.eddgraph',
    'try-merge-recovery-record-v1.eddgraph',
    'recover-record-channel-v1.eddgraph',
    'recover-repository-records-v1.eddgraph',
    'commit-recovered-repository-v1.eddgraph',
    'load-repository-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $repositoryRecordRecoveryLive $graphName)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryRecordRecoveryContracts.py') `
    --project-root $ProjectRoot --input-dir $repositoryRecordRecoveryLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository record-recovery live contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot --input-dir (Join-Path $ProjectRoot 'tools\blueprint\snippets')
if ($LASTEXITCODE -ne 0) {
    throw "Checked-in repository document encoder contracts failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path (Join-Path $ProjectRoot 'tools\blueprint\live-snippets\encode-waypoint-v1.eddgraph')
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets') `
    --only waypoint
if ($LASTEXITCODE -ne 0) {
    throw "Live EncodeWaypointV1 contracts failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path (Join-Path $ProjectRoot 'tools\blueprint\live-snippets\encode-segment-v1.eddgraph')
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets') `
    --only segment
if ($LASTEXITCODE -ne 0) {
    throw "Live EncodeSegmentV1 contracts failed with exit code $LASTEXITCODE."
}
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
    -Path (Join-Path $ProjectRoot 'tools\blueprint\live-snippets\encode-document-v1.eddgraph')
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentEncoderContracts.py') `
    --project-root $ProjectRoot `
    --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets') `
    --only document
if ($LASTEXITCODE -ne 0) {
    throw "Live EncodeDocumentV1 contracts failed with exit code $LASTEXITCODE."
}

foreach ($decoderName in @('waypoint', 'segment', 'document')) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $ProjectRoot "tools\blueprint\live-snippets\decode-$decoderName-v1.eddgraph")
    if ($LASTEXITCODE -ne 0) {
        throw "Live Decode$decoderName V1 graph structure failed with exit code $LASTEXITCODE."
    }
    & python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryDocumentDecoderContracts.py') `
        --project-root $ProjectRoot `
        --input-dir (Join-Path $ProjectRoot 'tools\blueprint\live-snippets') `
        --only $decoderName
    if ($LASTEXITCODE -ne 0) {
        throw "Live Decode$decoderName V1 contracts failed with exit code $LASTEXITCODE."
    }
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

$repositoryPrivateLoadNonce = [guid]::NewGuid().ToString('N')
$repositoryPrivateLoadRoot = Join-Path $scratchRoot "edd-repository-private-load-$repositoryPrivateLoadNonce"
$repositoryPrivateLoadFull = Join-Path $repositoryPrivateLoadRoot 'full'
$repositoryPrivateLoadPaste = Join-Path $repositoryPrivateLoadRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPrivateLoadFull, $repositoryPrivateLoadPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPrivateDraftLoadGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPrivateLoadFull `
    --paste-dir $repositoryPrivateLoadPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-load graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPrivateLoadFull, $repositoryPrivateLoadPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDraftLoadContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateLoadFull 'load-draft-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-load full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDraftLoadContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateLoadPaste 'load-draft-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-load paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPrivateLoadFull 'load-draft-v1.eddgraph'), 'tools\blueprint\snippets\load-draft-v1.eddgraph'),
    @((Join-Path $repositoryPrivateLoadPaste 'load-draft-v1-paste.eddgraph'), 'tools\blueprint\snippets\load-draft-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository private-load graph is not deterministic: $($pair[1])"
    }
}
$repositoryPrivateLoadLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\load-draft-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPrivateLoadLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDraftLoadContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPrivateLoadLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-load live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPublishedFetchNonce = [guid]::NewGuid().ToString('N')
$repositoryPublishedFetchRoot = Join-Path $scratchRoot "edd-repository-published-fetch-$repositoryPublishedFetchNonce"
$repositoryPublishedFetchFull = Join-Path $repositoryPublishedFetchRoot 'full'
$repositoryPublishedFetchPaste = Join-Path $repositoryPublishedFetchRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPublishedFetchFull, $repositoryPublishedFetchPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPublishedFetchGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPublishedFetchFull `
    --paste-dir $repositoryPublishedFetchPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-fetch graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPublishedFetchFull, $repositoryPublishedFetchPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishedFetchContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishedFetchFull 'fetch-published-revision-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-fetch full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishedFetchContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishedFetchPaste 'fetch-published-revision-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-fetch paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPublishedFetchFull 'fetch-published-revision-v1.eddgraph'), 'tools\blueprint\snippets\fetch-published-revision-v1.eddgraph'),
    @((Join-Path $repositoryPublishedFetchPaste 'fetch-published-revision-v1-paste.eddgraph'), 'tools\blueprint\snippets\fetch-published-revision-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository published-fetch graph is not deterministic: $($pair[1])"
    }
}
$repositoryPublishedFetchLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\fetch-published-revision-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPublishedFetchLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishedFetchContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPublishedFetchLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-fetch live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPublishedCloneNonce = [guid]::NewGuid().ToString('N')
$repositoryPublishedCloneRoot = Join-Path $scratchRoot "edd-repository-published-clone-$repositoryPublishedCloneNonce"
$repositoryPublishedCloneFull = Join-Path $repositoryPublishedCloneRoot 'full'
$repositoryPublishedClonePaste = Join-Path $repositoryPublishedCloneRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPublishedCloneFull, $repositoryPublishedClonePaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryClonePublishedGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPublishedCloneFull `
    --paste-dir $repositoryPublishedClonePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-clone graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPublishedCloneFull, $repositoryPublishedClonePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryClonePublishedContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishedCloneFull 'clone-published-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-clone full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryClonePublishedContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishedClonePaste 'clone-published-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-clone paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPublishedCloneFull 'clone-published-v1.eddgraph'), 'tools\blueprint\snippets\clone-published-v1.eddgraph'),
    @((Join-Path $repositoryPublishedClonePaste 'clone-published-v1-paste.eddgraph'), 'tools\blueprint\snippets\clone-published-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository published-clone graph is not deterministic: $($pair[1])"
    }
}
$repositoryPublishedCloneLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\clone-published-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPublishedCloneLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryClonePublishedContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPublishedCloneLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository published-clone live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPrivateCreateNonce = [guid]::NewGuid().ToString('N')
$repositoryPrivateCreateRoot = Join-Path $scratchRoot "edd-repository-private-create-$repositoryPrivateCreateNonce"
$repositoryPrivateCreateFull = Join-Path $repositoryPrivateCreateRoot 'full'
$repositoryPrivateCreatePaste = Join-Path $repositoryPrivateCreateRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPrivateCreateFull, $repositoryPrivateCreatePaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPrivateCreateGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPrivateCreateFull `
    --paste-dir $repositoryPrivateCreatePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-create graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPrivateCreateFull, $repositoryPrivateCreatePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateCreateContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateCreateFull 'create-private-flypath-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-create full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateCreateContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateCreatePaste 'create-private-flypath-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-create paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPrivateCreateFull 'create-private-flypath-v1.eddgraph'), 'tools\blueprint\snippets\create-private-flypath-v1.eddgraph'),
    @((Join-Path $repositoryPrivateCreatePaste 'create-private-flypath-v1-paste.eddgraph'), 'tools\blueprint\snippets\create-private-flypath-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository private-create graph is not deterministic: $($pair[1])"
    }
}
$repositoryPrivateCreateLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\create-private-flypath-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPrivateCreateLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateCreateContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPrivateCreateLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-create live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPrivateSaveNonce = [guid]::NewGuid().ToString('N')
$repositoryPrivateSaveRoot = Join-Path $scratchRoot "edd-repository-private-save-$repositoryPrivateSaveNonce"
$repositoryPrivateSaveFull = Join-Path $repositoryPrivateSaveRoot 'full'
$repositoryPrivateSavePaste = Join-Path $repositoryPrivateSaveRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPrivateSaveFull, $repositoryPrivateSavePaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPrivateSaveGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPrivateSaveFull `
    --paste-dir $repositoryPrivateSavePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-save graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPrivateSaveFull, $repositoryPrivateSavePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateSaveContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateSaveFull 'save-draft-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-save full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateSaveContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateSavePaste 'save-draft-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-save paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPrivateSaveFull 'save-draft-v1.eddgraph'), 'tools\blueprint\snippets\save-draft-v1.eddgraph'),
    @((Join-Path $repositoryPrivateSavePaste 'save-draft-v1-paste.eddgraph'), 'tools\blueprint\snippets\save-draft-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository private-save graph is not deterministic: $($pair[1])"
    }
}
$repositoryPrivateSaveLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\save-draft-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPrivateSaveLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateSaveContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPrivateSaveLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-save live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPrivateListNonce = [guid]::NewGuid().ToString('N')
$repositoryPrivateListRoot = Join-Path $scratchRoot "edd-repository-private-list-$repositoryPrivateListNonce"
$repositoryPrivateListFull = Join-Path $repositoryPrivateListRoot 'full'
$repositoryPrivateListPaste = Join-Path $repositoryPrivateListRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPrivateListFull, $repositoryPrivateListPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPrivateListGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPrivateListFull `
    --paste-dir $repositoryPrivateListPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-list graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPrivateListFull, $repositoryPrivateListPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateListContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryPrivateListFull
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-list full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateListContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryPrivateListPaste `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-list paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPrivateListFull 'compare-strings-ordinal-v1.eddgraph'), 'tools\blueprint\snippets\compare-strings-ordinal-v1.eddgraph'),
    @((Join-Path $repositoryPrivateListFull 'encode-metadata-v1.eddgraph'), 'tools\blueprint\snippets\encode-metadata-v1.eddgraph'),
    @((Join-Path $repositoryPrivateListFull 'list-mine-v1.eddgraph'), 'tools\blueprint\snippets\list-mine-v1.eddgraph'),
    @((Join-Path $repositoryPrivateListPaste 'compare-strings-ordinal-v1-paste.eddgraph'), 'tools\blueprint\snippets\compare-strings-ordinal-v1-paste.eddgraph'),
    @((Join-Path $repositoryPrivateListPaste 'encode-metadata-v1-paste.eddgraph'), 'tools\blueprint\snippets\encode-metadata-v1-paste.eddgraph'),
    @((Join-Path $repositoryPrivateListPaste 'list-mine-v1-paste.eddgraph'), 'tools\blueprint\snippets\list-mine-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository private-list graph is not deterministic: $($pair[1])"
    }
}
foreach ($graph in @(
    'compare-strings-ordinal-v1.eddgraph',
    'encode-metadata-v1.eddgraph',
    'list-mine-v1.eddgraph'
)) {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') `
        -Path (Join-Path $repositoryCoreLive $graph)
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateListContracts.py') `
    --project-root $ProjectRoot `
    --input-dir $repositoryCoreLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-list live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPublicListNonce = [guid]::NewGuid().ToString('N')
$repositoryPublicListRoot = Join-Path $scratchRoot "edd-repository-public-list-$repositoryPublicListNonce"
$repositoryPublicListFull = Join-Path $repositoryPublicListRoot 'full'
$repositoryPublicListPaste = Join-Path $repositoryPublicListRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPublicListFull, $repositoryPublicListPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPublicListGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPublicListFull `
    --paste-dir $repositoryPublicListPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository public-list graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPublicListFull, $repositoryPublicListPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublicListContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublicListFull 'list-public-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository public-list full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublicListContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublicListPaste 'list-public-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository public-list paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPublicListFull 'list-public-v1.eddgraph'), 'tools\blueprint\snippets\list-public-v1.eddgraph'),
    @((Join-Path $repositoryPublicListPaste 'list-public-v1-paste.eddgraph'), 'tools\blueprint\snippets\list-public-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository public-list graph is not deterministic: $($pair[1])"
    }
}
$repositoryPublicListLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\list-public-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPublicListLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublicListContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPublicListLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository public-list live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPrivateDeleteNonce = [guid]::NewGuid().ToString('N')
$repositoryPrivateDeleteRoot = Join-Path $scratchRoot "edd-repository-private-delete-$repositoryPrivateDeleteNonce"
$repositoryPrivateDeleteFull = Join-Path $repositoryPrivateDeleteRoot 'full'
$repositoryPrivateDeletePaste = Join-Path $repositoryPrivateDeleteRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPrivateDeleteFull, $repositoryPrivateDeletePaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPrivateDeleteGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPrivateDeleteFull `
    --paste-dir $repositoryPrivateDeletePaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-delete graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPrivateDeleteFull, $repositoryPrivateDeletePaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDeleteContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateDeleteFull 'delete-flypath-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-delete full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDeleteContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPrivateDeletePaste 'delete-flypath-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-delete paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPrivateDeleteFull 'delete-flypath-v1.eddgraph'), 'tools\blueprint\snippets\delete-flypath-v1.eddgraph'),
    @((Join-Path $repositoryPrivateDeletePaste 'delete-flypath-v1-paste.eddgraph'), 'tools\blueprint\snippets\delete-flypath-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository private-delete graph is not deterministic: $($pair[1])"
    }
}
$repositoryPrivateDeleteLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\delete-flypath-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPrivateDeleteLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPrivateDeleteContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPrivateDeleteLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository private-delete live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryPublishDraftNonce = [guid]::NewGuid().ToString('N')
$repositoryPublishDraftRoot = Join-Path $scratchRoot "edd-repository-publish-draft-$repositoryPublishDraftNonce"
$repositoryPublishDraftFull = Join-Path $repositoryPublishDraftRoot 'full'
$repositoryPublishDraftPaste = Join-Path $repositoryPublishDraftRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryPublishDraftFull, $repositoryPublishDraftPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryPublishDraftGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryPublishDraftFull `
    --paste-dir $repositoryPublishDraftPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository publish-draft graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryPublishDraftFull, $repositoryPublishDraftPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishDraftContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishDraftFull 'publish-draft-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository publish-draft full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishDraftContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryPublishDraftPaste 'publish-draft-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository publish-draft paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryPublishDraftFull 'publish-draft-v1.eddgraph'), 'tools\blueprint\snippets\publish-draft-v1.eddgraph'),
    @((Join-Path $repositoryPublishDraftPaste 'publish-draft-v1-paste.eddgraph'), 'tools\blueprint\snippets\publish-draft-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository publish-draft graph is not deterministic: $($pair[1])"
    }
}
$repositoryPublishDraftLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\publish-draft-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryPublishDraftLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryPublishDraftContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryPublishDraftLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository publish-draft live-round-trip contracts failed with exit code $LASTEXITCODE."
}

$repositoryUnpublishNonce = [guid]::NewGuid().ToString('N')
$repositoryUnpublishRoot = Join-Path $scratchRoot "edd-repository-unpublish-$repositoryUnpublishNonce"
$repositoryUnpublishFull = Join-Path $repositoryUnpublishRoot 'full'
$repositoryUnpublishPaste = Join-Path $repositoryUnpublishRoot 'paste'
New-Item -ItemType Directory -Force -Path $repositoryUnpublishFull, $repositoryUnpublishPaste | Out-Null
& python (Join-Path $ProjectRoot 'tools\blueprint\Build-RepositoryUnpublishGraph.py') `
    --project-root $ProjectRoot `
    --output-dir $repositoryUnpublishFull `
    --paste-dir $repositoryUnpublishPaste
if ($LASTEXITCODE -ne 0) {
    throw "Repository unpublish graph generation failed with exit code $LASTEXITCODE."
}
foreach ($graph in Get-ChildItem -LiteralPath $repositoryUnpublishFull, $repositoryUnpublishPaste -Filter '*.eddgraph') {
    & (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $graph.FullName
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryUnpublishContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryUnpublishFull 'unpublish-v1.eddgraph')
if ($LASTEXITCODE -ne 0) {
    throw "Repository unpublish full contracts failed with exit code $LASTEXITCODE."
}
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryUnpublishContracts.py') `
    --project-root $ProjectRoot `
    --input (Join-Path $repositoryUnpublishPaste 'unpublish-v1-paste.eddgraph') `
    --paste
if ($LASTEXITCODE -ne 0) {
    throw "Repository unpublish paste contracts failed with exit code $LASTEXITCODE."
}
foreach ($pair in @(
    @((Join-Path $repositoryUnpublishFull 'unpublish-v1.eddgraph'), 'tools\blueprint\snippets\unpublish-v1.eddgraph'),
    @((Join-Path $repositoryUnpublishPaste 'unpublish-v1-paste.eddgraph'), 'tools\blueprint\snippets\unpublish-v1-paste.eddgraph')
)) {
    $checkedIn = Join-Path $ProjectRoot $pair[1]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $pair[0]).Hash -ne
        (Get-FileHash -Algorithm SHA256 -LiteralPath $checkedIn).Hash) {
        throw "Repository unpublish graph is not deterministic: $($pair[1])"
    }
}
$repositoryUnpublishLive = Join-Path $ProjectRoot 'tools\blueprint\live-snippets\unpublish-v1.eddgraph'
& (Join-Path $ProjectRoot 'tools\blueprint\Test-BlueprintGraphSnippet.ps1') -Path $repositoryUnpublishLive
& python (Join-Path $ProjectRoot 'tools\blueprint\Test-RepositoryUnpublishContracts.py') `
    --project-root $ProjectRoot `
    --input $repositoryUnpublishLive
if ($LASTEXITCODE -ne 0) {
    throw "Repository unpublish live-round-trip contracts failed with exit code $LASTEXITCODE."
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
