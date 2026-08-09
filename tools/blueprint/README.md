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
- `Test-WaypointCaptureContracts.py` verifies exact array types, data sources,
  append order, selected-index assignment, ID increment, and available
  EventGraph dispatch semantics.
- `Test-WaypointEditContracts.py` verifies guarded replacement, stable ID/hold,
  ordered six-channel removal, and deterministic post-delete selection.

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

Design comment nodes exported by Unreal use
`/Script/UnrealEd.EdGraphNode_Comment`; the snippet validator permits that one
documentation class in addition to executable `/Script/BlueprintGraph.*`
nodes.

Authoritative workflow and safety rules live in
`docs/blueprint-workflow.md`.
