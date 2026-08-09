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
- `cache-original-pawn.eddgraph` captures typed `OriginalPawnRef` from local
  Player Pawn 0 before Drone Mode changes controller ownership.
- `possess-drone-camera.eddgraph` guards `DroneCameraRef` and possesses it with
  local Player Controller 0.
- `restore-original-possession.eddgraph` restores a valid `OriginalPawnRef`, or
  safely calls `UnPossess` when the entry context had no pawn.
- `activate-drone-view.eddgraph` caches the original pawn, caches the original
  local view target once, and delegates both view-cache outcomes to the switch.
- `switch-to-drone-view.eddgraph` guards and possesses `DroneCameraRef` before
  switching local Player Controller 0 through `SetViewTargetWithBlend`.
- `exit-drone-mode.eddgraph` restores controller possession first, then guards
  `OriginalViewTargetRef` and restores the same local view through the paired
  engine API.
- `emergency-exit-drone-mode.eddgraph` idempotently delegates normal view
  restoration, forces `DroneModeActive` false, then logs completion.
- `client-director-event-graph.eddgraph` owns the complete executable client
  dispatch: F10 normal entry/exit, F9 manual emergency exit, and automatic
  emergency restoration when an active drone camera becomes invalid. A valid
  active drone delegates translation to `ApplyTranslationInput`.
- `apply-translation-input.eddgraph` samples W/S, D/A, and E/Q, constructs three
  signed local axes, and chains forced forward/right/up movement input.

Design comment nodes exported by Unreal use
`/Script/UnrealEd.EdGraphNode_Comment`; the snippet validator permits that one
documentation class in addition to executable `/Script/BlueprintGraph.*`
nodes.

Authoritative workflow and safety rules live in
`docs/blueprint-workflow.md`.
