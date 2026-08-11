# Blueprint graph tooling

The Enhanced DevKit exposes Blueprint assets, variables, components, compile,
and save operations to Python, but it does not expose concrete K2 node creation.
Exile Drone Director therefore uses Unreal's native Blueprint clipboard format
for reviewed batches of graph nodes.

The tools in this directory never launch Unreal:

- `Export-BlueprintGraphClipboard.ps1` captures selected nodes copied from the
  Blueprint editor into a normalized `.eddgraph` source file.
- `Test-BlueprintGraphSnippet.ps1` validates node boundaries, identifiers,
  internal links, node classes, and the mod namespace.
- `Test-BlueprintGraphContracts.ps1` verifies the semantic wiring contract of
  every checked-in snippet, including execution order and diagnostic source.
- `Set-BlueprintGraphClipboard.ps1` resolves explicit `{{TOKEN}}` placeholders
  and places the graph on the Windows clipboard for pasting in Unreal.
- `Build-RollInputGraph.py` composes manual bank, H toggle, held-input
  arbitration, and smooth world-up horizon stabilization from reviewed
  mod-owned node forms. Its paste output deliberately leaves the first exec pin
  unlinked so the existing live function entry must be connected explicitly.
- `Build-ClientRollDispatch.py` appends the ordered camera call to a pre-roll
  client graph and is byte-for-byte idempotent once exactly one roll dispatch
  already exists.
- `Build-WaypointCaptureGraph.py` composes the six-channel atomic capture
  function from live-harvested, mod-owned node forms and emits both complete and
  body-only graphs with reproducible identifiers.
- `Build-ClientWaypointDispatch.py` appends the guarded K-edge capture call
  after roll/horizon processing and is byte-for-byte deterministic and
  idempotent.
- `Build-WaypointEditGraphs.py` composes guarded replace and six-channel atomic
  delete functions from live-harvested node forms.
- `Build-ClientWaypointEditDispatch.py` extends the proven K capture tail with
  mutually exclusive R replace and Delete removal edge polls.
- `Build-WaypointFeedbackDispatch.py` extends that reviewed mutation dispatch
  with one shared dynamic count/selection message and a distinct terminal print
  after each successful mutation.
- `Build-LinearPlaybackGraphs.py` composes guarded start, absolute-time
  equal-duration traversal, exact endpoint completion, and explicit stop graphs
  from Unreal-reconstructed node forms.
- `Build-PathPreviewLifecycleGraphs.py` composes deterministic refresh/reuse and
  clear/destroy functions for the client-owned preview reference, including the
  explicit identity transform required by Enhanced's by-reference spawn pin.
- `Build-PathPreviewIntegrationGraphs.py` upgrades the reviewed Enter, Exit,
  Capture, Replace, and Delete baselines with full-document sync and preview
  lifecycle calls while preserving body-only paste forms.
- `Build-RepositoryCoreGraphs.py` deterministically composes the repository
  result-reset and flypath-ID lookup functions from reviewed mod-owned node
  forms. It emits complete contract graphs and body-only paste graphs; the
  latter intentionally require one explicit native function-entry exec wire.
- `repository-json-node-forms.eddgraph` is the native-round-trip Enhanced 5.6
  PlayFab JSON fixture. `Test-RepositoryJsonNodeForms.py` locks its 15 callable
  signatures, pin types, purity, and impure array-getter behavior.
- `Build-RepositoryJsonMissingNodeProbe.py` reconstructs the three reflected
  calls that the global action menu hides (`HasField`, `EncodeJson`, and
  `DecodeJson`) for disposable compile/copy-back validation.
- `Test-WaypointCaptureContracts.py` verifies exact array types, data sources,
  append order, selected-index assignment, ID increment, and available
  EventGraph dispatch semantics.
- `Test-WaypointEditContracts.py` verifies guarded replacement, stable ID/hold,
  ordered six-channel removal, and deterministic post-delete selection.
- `Test-WaypointFeedbackContracts.py` verifies that count and selection are
  derived from live state and displayed after capture, replace, and delete.
- `Test-LinearPlaybackContracts.py` verifies the time source, segment math,
  quaternion transform lerp, exact final endpoint, selection, and stop state.
- `Test-PathPreviewLifecycleContracts.py` verifies create/reuse symmetry,
  document projection, explicit spawn input, clear-before-destroy, stale
  reference cleanup, and native function-entry reachability.
- `Test-PathPreviewIntegrationContracts.py` verifies all five production roots,
  every success-path refresh, full-document sync, feedback ordering, and
  destroy-before-view-restoration.
- `Test-RepositoryCoreContracts.py` verifies exact result defaults, metadata
  clearing, derived-index lookup, staged request use, execution reachability,
  and closed graph links for both complete and paste-safe forms.

Validated snippets:

- `toggle-input.eddgraph` owns edge-triggered local key polling and exposes
  `INPUT_KEY` and `DIAGNOSTIC_TEXT` tokens.
- `toggle-state.eddgraph` owns exactly one state transition. Its unlinked Set
  execution pin is the caller entry point; it writes
  `DroneModeActive = NOT DroneModeActive`, then logs the post-set value.
- `enter-drone-mode.eddgraph` guards and reuses a typed drone camera reference,
  spawning exactly one camera when necessary, placing it, then delegating
  activation.
- `place-drone-at-current-view.eddgraph` guards `DroneCameraRef`, samples local
  Player Camera Manager 0, and atomically copies its evaluated world location
  and rotation to the drone before view activation.
- `cache-original-pawn.eddgraph`, `possess-drone-camera.eddgraph`, and
  `restore-original-possession.eddgraph` preserve the rejected native-movement
  experiment for auditability. They remain structurally validated but are not
  called by the production switch/exit path.
- `activate-drone-view.eddgraph` caches the original local view target once and
  delegates both view-cache outcomes to the switch. Its legacy pawn-cache call
  is inert with respect to controller ownership and will be removed during the
  next lifecycle cleanup.
- `switch-to-drone-view.eddgraph` guards `DroneCameraRef` and switches local
  Player Controller 0 through `SetViewTargetWithBlend` without possession.
- `exit-drone-mode.eddgraph` guards `OriginalViewTargetRef` and restores that
  exact local view without changing possession.
- `emergency-exit-drone-mode.eddgraph` idempotently delegates normal view
  restoration, forces `DroneModeActive` false, then logs completion.
- `client-director-event-graph.eddgraph` owns the complete executable client
  dispatch behind an owning-local-controller identity gate: F10 normal
  entry/exit, F9 manual emergency exit, and automatic restoration when an active
  drone camera becomes invalid. A valid active drone delegates speed evaluation
  to `UpdateSpeedControls`, translation to `ApplyTranslationInput`, then
  mouse rotation to `ApplyRotationInput`, then manual bank to
  `ApplyRollAndHorizonInput`, then K-edge waypoint capture on the same guarded
  tick.
- `capture-current-waypoint.eddgraph` validates `DroneCameraRef`, appends the
  current ID, transform, focal length, aperture, focus distance, and zero hold
  time atomically, selects the appended index, advances `NextWaypointId`, and
  emits its development diagnostic.
- `replace-selected-waypoint.eddgraph` validates camera and selected ID index,
  then replaces transform and lens channels without changing stable ID or hold.
- `delete-selected-waypoint.eddgraph` removes the selected item from all six
  arrays and preserves or clamps selection after the mutation.
- `apply-translation-input.eddgraph` samples W/S, D/A, and E/Q, constructs three
  signed local axes, scales one vector by the smoothed `CurrentMoveSpeed` and
  world delta time, and applies one local actor offset.
- `apply-rotation-input.eddgraph` samples Player Controller 0 mouse delta,
  scales yaw by `LookSensitivity`, scales pitch by the negated sensitivity,
  preserves zero roll, and applies one local actor rotation without sweep or
  teleport.
- `apply-roll-and-horizon-input.eddgraph` samples C-minus-Z as a signed bank
  axis, eases `CurrentRollSpeed` toward `ManualRollSpeed * axis`, and gives held
  C/Z precedence over stabilization. H edge-toggles `HorizonLockEnabled`; idle
  locked frames build a level target from current forward plus explicit
  `(0,0,1)` world up, then `RInterpTo` with `HorizonLockResponse` before one
  absolute world-rotation write. Disabled lock preserves bank while residual
  speed decays through the manual local-rotation path.
- `update-speed-controls.eddgraph` applies proportional mouse-wheel cruise trim,
  clamps it to the configured speed range, gives Ctrl precision precedence over
  Shift boost, and eases `CurrentMoveSpeed` toward the selected target with
  `FInterpTo`. Its contract explicitly requires the computed trim value to be
  connected to the clamp, preventing a valid-looking graph from collapsing to
  `MinMoveSpeed` at runtime.
- `drone-camera-event-graph.eddgraph` explicitly disables actor and movement
  replication at BeginPlay to override `SpectatorPawn`'s inherited runtime state.
- `refresh-path-preview-v1.eddgraph` and `destroy-path-preview-v1.eddgraph` are
  the checked post-compile Unreal lifecycle round-trips.
- `*-preview.eddgraph` for Enter, Exit, Capture, Replace, and Delete are the
  checked production round-trips. The unsuffixed versions remain deterministic
  construction baselines for the integration builder.

Design comment nodes exported by Unreal use
`/Script/UnrealEd.EdGraphNode_Comment`; the snippet validator permits that one
documentation class in addition to executable `/Script/BlueprintGraph.*`
nodes.

Authoritative workflow and safety rules live in
`docs/blueprint-workflow.md`.
