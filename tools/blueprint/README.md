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
  spawning exactly one camera when necessary before delegating activation.
- `activate-drone-view.eddgraph` caches the original local view target once and
  delegates both cache outcomes to the view switch.
- `switch-to-drone-view.eddgraph` guards `DroneCameraRef` and switches local
  Player Controller 0 through `SetViewTargetWithBlend`.
- `exit-drone-mode.eddgraph` guards `OriginalViewTargetRef` and restores the
  same local controller through the paired engine API.

Authoritative workflow and safety rules live in
`docs/blueprint-workflow.md`.
