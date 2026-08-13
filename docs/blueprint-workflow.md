# Blueprint Graph Workflow

## Purpose

Exile Drone Director is Blueprint-only. The Enhanced DevKit's Python API can
create assets, variables, components, input assets, and structs, then compile
and save them. It can locate an Event Graph, but it does not expose concrete K2
node constructors or graph insertion methods.

Graph implementation therefore uses Unreal's native clipboard serialization as
a development source format. This avoids treating slow, coordinate-dependent
mouse automation as the primary authoring method while keeping every runtime
asset as a normal, inspectable Blueprint.

## Authoring loop

Launch the interactive editor with the Conan project **and** `-ModDevKit`.
Without that flag the editor does not mount `/Game/Mods/ExileDroneDirector`, so
Blueprint automation will report that valid mod assets cannot be loaded.

Before launching a fresh Enhanced editor installation, provision the persistent
local remote endpoint once (the helper is idempotent):

```powershell
.\tools\unreal\Enable-EnhancedEditorRemoteExecution.ps1 `
  -DevKitRoot F:\CEUE5Devkit
```

The effective section is `PythonScriptPluginSettings` in generated
`WindowsEditor/Engine.ini`. Do not place these values under the similarly named
user-settings class or `EditorPerProjectUserSettings.ini`; both were observed to
load Python without starting the remote endpoint. After launch, require exactly
one matching `ConanSandbox` discovery node before sending any mutating script.

1. Create the smallest new node pattern in a mod-owned Blueprint using the
   visible editor.
2. Compile and prove that pattern in PIE before turning it into a template.
3. Select only the proven nodes and copy them with `Ctrl+C`.
4. Export the clipboard into `tools/blueprint/snippets/*.eddgraph`:

   ```powershell
   .\tools\blueprint\Export-BlueprintGraphClipboard.ps1 `
     -DestinationPath .\tools\blueprint\snippets\toggle-drone.eddgraph
   ```

5. Review the textual graph, reduce it to one responsibility, and replace only
   intentional default values with uppercase `{{TOKENS}}`.
6. Validate the snippet offline:

   ```powershell
   .\tools\blueprint\Test-BlueprintGraphSnippet.ps1 `
     -Path .\tools\blueprint\snippets\toggle-drone.eddgraph `
     -AllowTokens
   ```

7. Resolve tokens and prepare it for paste:

   ```powershell
   .\tools\blueprint\Set-BlueprintGraphClipboard.ps1 `
     -SnippetPath .\tools\blueprint\snippets\toggle-drone.eddgraph `
     -Token @{ DIAGNOSTIC_TEXT = '[EDD] Drone mode toggled' }
   ```

8. Paste once into the intended mod-owned graph, compile immediately, inspect
   warnings, save, and run the snippet's acceptance test.
9. Run the semantic contract suite before committing graph source:

   ```powershell
   .\tools\blueprint\Test-BlueprintGraphContracts.ps1
   ```

## Rules

- Never paste or save nodes into a Conan base-game asset.
- A snippet has one responsibility and one documented acceptance signal.
- Source graph exports must belong to `/Game/Mods/ExileDroneDirector/`.
- Physical mod assets live beneath `Content/Mods/ExileDroneDirector/Local`, but
  the Conan `-ModDevKit` platform layer exposes that tree at
  `/Game/Mods/ExileDroneDirector/...`. Always load assets through that virtual
  root. If the Content Browser instead exposes `/Game/Mods/ExileDroneDirector/Local/...`,
  the editor was launched without `-ModDevKit`; close it without saving and
  relaunch correctly before opening any mod package.
- Never hand-edit `NodeGuid`, `PinId`, or `LinkedTo` relationships casually.
- Do not paste a snippet twice unless it is explicitly designed to be repeated.
- Compile after every paste; do not accumulate multiple unverified graph batches.
- Before promoting an accepted `.uasset`, close the GUI editor and run
  `tools/Test-ColdAssetLoad.ps1`. A warm PIE pass is not evidence that every
  package dependency resolves after restart.
- Never sync `.uasset` files while Unreal is open. For repository promotion,
  stop PIE, compile/save, close every DevKit window, wait for
  `LogExit: Exiting.`, then sync `FromDevKit`. Sync `ToDevKit` only before the
  next editor launch.
- If a paste intentionally excludes an existing function-entry node, reconnect
  that entry in the live graph and export the complete graph again. A one-sided
  serialized external link can compile green while leaving the function body
  unreachable; the checked-in contract must require both reciprocal exec links.
- Unreal may insert `MemberGuid` between a Blueprint function/variable name and
  `bSelfContext=True` during paste/compile round-trip. Semantic tests match the
  stable member identity and then prove exact reciprocal links; they do not
  require a fragile byte sequence that rejects this valid native normalization.
- This DevKit's Python surface has no world-specific generic actor-spawn call,
  and editor actor spawning is rejected while PIE is active. Runtime harnesses
  that need a standalone actor must place a temporary non-transient actor before
  PIE, verify exactly one duplicated actor in the PIE world, destroy the editor
  source after PIE, restore all seeded class defaults, and never save the dirty
  test level/package.
- Runtime state machines live in named Blueprint functions or components, not a
  monolithic Event Graph.
- Pure Blueprint expressions are reevaluated for each consumer. If several
  mutating nodes share an index such as `Length(Array) - 1`, either materialize
  it before mutation or keep the measured array unchanged until every consumer
  has executed. Semantic contracts must lock the required mutation order.
- PIE evidence is recorded in `docs/devkit-findings.md` before a diagnostic node
  is removed or generalized.
- A graph screenshot is supporting evidence only. Checked-in node serialization
  proves links; compile/save proves asset validity; PIE proves runtime behavior.
- Snippet execution inputs must be intentionally internal or intentionally
  unlinked and documented as public caller entry points. Dangling external links
  are rejected.
- Camera work never moves the player character and never changes controller
  possession. The verified backend switches only the local view target and
  integrates the non-replicated drone transform explicitly with world delta time.
- Every director component must prove `Owner == GetPlayerController(0)` before
  reading local input. A non-local component terminates the tick with no side
  effects.
- `SpectatorPawn` inheritance can force replication at runtime. The drone's
  BeginPlay graph must explicitly call `SetReplicates(false)` followed by
  `SetReplicateMovement(false)`; class-default inspection alone is insufficient.

## Resource profile

The export, validation, templating, documentation, and repository tests are
lightweight and do not launch Unreal. Asset compilation, PIE, and cooking still
load the Enhanced DevKit and must not run alongside a resource-heavy game.

## First planned snippets

1. Client-director BeginPlay diagnostic. **Proven in PIE.**
2. Toggle-key edge detection and state transition. **Proven in PIE with two
   presses producing `true`, then `false`.**
3. Spawn one local drone and reuse its typed cached reference. **Proven in PIE:
   first entry spawned it and the next entry reused it.**
4. Cache the original local view target once. **Proven in PIE: first entry
   cached it and the next entry reused it.**
5. Guard and switch the local view to the drone, then restore the cached player
   view. **Proven in PIE across enter, exit, cached re-entry, and second exit.**
6. Place the drone at the current camera before the local view switch.
   **Proven in PIE on both initial spawn and cached-camera reuse, with exact
   location/rotation equality before both switches.**
7. Emergency restoration, teardown recovery, and drone destruction.
   **Proven in PIE for repeatable manual F9 restoration and forced destruction
   of the active drone actor. Death, teleport, disconnect, and component
   end-play hooks remain pending.**
8. Six-axis transform integration. **Proven in two-player listen-server PIE:
   W/S, D/A, and E/Q form signed local axes, scale by smoothed
   `CurrentMoveSpeed` and world delta time, and apply one local offset. Host and
   remote-client movement stayed isolated, controlled pawns were unchanged, and
   exit restored the exact prior view target.**
9. Local mouse look. **Implemented as a nine-node named function: mouse delta
   from local Player Controller 0, configurable sensitivity, inverted pitch,
   zero roll, and one actor-local rotation. It compiles, round-trips, and is
   dispatched only after translation behind the existing owner/locality guards.
   Host yaw and cross-world isolation were observed in PIE; a real-mouse client
   pitch/yaw feel pass remains pending because synthetic input does not reach the
   separate preview's raw-input channel.**
10. Smooth speed controls. **Proven in the deterministic two-player fixture:
    baseline held at 600, a short boost eased to 1427, sustained boost reached
    1799, precision reached 151, and Ctrl won when Ctrl+Shift were held. One
    second of W travelled about 610 units normally, 1643 while boosting, and
    221 while easing into precision. Remote-client boost left the host drone
    exactly unchanged. Mouse-wheel topology and proportional inverse math are
    structurally checked; synthetic Windows wheel messages do not enter Conan's
    mouse-input channel, so physical-wheel feel remains a manual gate.**
11. Smooth manual roll and horizon lock. **Proven in the deterministic
    two-player fixture: C
    banked the host from 0 to +71.77 degrees, release speed decayed from 9.30 to
    approximately zero, and Z produced the opposite signed speed and returned
    bank near level. The remote client then banked independently to +71.27
    degrees while the host remained exactly unchanged. Both F9 exits restored
    the original pawn/view target. H now edge-toggles horizon lock; held C/Z
    overrides it, disabled lock preserves bank, and enabled lock eases the
    camera toward explicit world up while preserving forward direction. A
    seeded pitch 20/yaw 45/roll 60 settled at pitch 20/yaw 45/roll 0.001354.
    The 33-node/116-pin function and 33-node client Event Graph are exported
    with reciprocal-link and explicit `(0,0,1)` world-up contracts.**
12. Atomic waypoint authoring core. **The named `CaptureCurrentWaypoint` function
    appends ID, transform, focal length, aperture, focus distance, and hold time
    to six lockstep draft arrays, selects the returned append index, then
    advances `NextWaypointId`. `ReplaceSelectedWaypoint` updates the five
    camera-state channels without changing stable ID or hold, while
    `DeleteSelectedWaypoint` removes every channel and deterministically clamps
    selection. Their complete live graphs round-tripped through Unreal, compiled
    green, and are guarded by valid camera/selection checks. The client EventGraph
    polls `K` with `WasInputKeyJustPressed` only after owner, active-mode,
    camera-validity, speed, translation, rotation, and roll processing. Two
    captures followed by replace/delete operations in deterministic two-player
    PIE produced IDs `[1,2]`, equal channel lengths, exact replacement values,
    valid survivor/empty selection, invalid-index no-ops, zero remote-client
    draft mutation, no leaked drone, exact view restoration, and restored class
    defaults.
    Real F10, K, R, Delete, and F9 input has now passed in two-player PIE. The
    live 51-node dispatch reports the dynamic waypoint count and selected index
    after every successful mutation. Its complete compiled graph was copied back
    from Unreal and is enforced by capture, edit, and feedback contracts.**
13. Client-owned path-preview lifecycle. **Add the typed
    `PathPreviewActorV1` reference and the empty `RefreshPathPreviewV1` /
    `DestroyPathPreviewV1` function seams with
    `Configure-PathPreviewLifecycle.py`. Generate both complete and paste forms
    with `Build-PathPreviewLifecycleGraphs.py`; the refresh graph must wire an
    explicit identity `MakeTransform` into the by-reference spawn input. Generate
    the five production integration graphs with
    `Build-PathPreviewIntegrationGraphs.py`, paste each body, and manually connect
    its native function entry. Compile, save, export every complete live graph,
    and require `Test-PathPreviewLifecycleContracts.py` plus
    `Test-PathPreviewIntegrationContracts.py` to pass before PIE. The final
    two-client lifecycle run proved create/reuse, document projection after real
    capture, playback coexistence, cleanup, fresh re-entry, and client isolation.**

When pasting a function body without its native `K2Node_FunctionEntry`, a
one-sided `LinkedTo` reference in pasted text is not enough. Unreal does not add
the reciprocal link to the pre-existing entry pin, so the function compiles as
an unreachable no-op. Move the native entry clear of overlapping pasted nodes,
wire it manually, copy the complete live graph back out, and require the exact
entry pin link in the semantic contract before runtime testing.

`Build-WaypointStructSyncGraph.py` encodes this boundary explicitly: its full
source graph contains the reciprocal entry link, while its paste artifact leaves
the first Branch execution input intentionally unlinked. After paste, connect
the native entry once, compile, export the complete live function, and run
`Test-WaypointStructSyncContracts.py` against that round-trip. Never use
`-AllowExternalFunctionEntry` to disguise an unreachable paste body.

The entry check is required for every production function, even when every
internal execution and data link is correct. During lifecycle integration,
Enter and Delete initially passed the inner-path contracts but did nothing from
their native roots because the final manual wire had not serialized. The
strengthened contracts now assert `FunctionEntry -> first executable node` for
all five integrated functions and caught both omissions before the accepted PIE
run.

Do not restart a deterministic Blueprint node-ID generator and paste its output
into a graph that may already contain nodes produced by the same sequence. The
resulting `NodeGuid`/`PinId` collisions can make Unreal silently attach or reject
links. Generate each complete graph in one run, paste only its intentionally
entryless body into an emptied function, and immediately export the native
round-trip. Also open functions by double-clicking their My Blueprint entry and
verify the breadcrumb before selecting or replacing nodes; a single-click can
leave the previous graph active without an obvious warning.

Each snippet is captured only after its live-editor version compiles and passes
its focused PIE check.

Mutation functions have an additional cinematic-feedback rule: accepted and
rejected diagnostics are log-only (`bPrintToScreen=false`,
`bPrintToLog=true`). The complete function body is generated in one pass, its
entryless variant is pasted into an emptied function, the native entry is wired
manually, and the fresh Unreal round-trip must pass
`Test-MutationDiagnosticContracts.py` together with history/document/preview
contracts. Rejected branches must terminate at their diagnostic and may not
reach history capture, mutation, document synchronization, or preview refresh.

Physical shortcut acceptance is an attended gate. Do not identify the game
viewport through `Get-Process.MainWindowHandle`: the editor, Blueprint editor,
Message Log, and Enhanced Preview can all be top-level windows in the same
process. More importantly, do not run focus-stealing key/mouse automation while
the computer is in use. Arm the PIE harness, let the operator focus the Enhanced
Preview explicitly, and follow its logged readiness markers.

`Export-BlueprintGraphClipboard.ps1` reads and validates the clipboard; it does
not drive Unreal or refresh the clipboard itself. Before every export, focus the
intended graph, select all nodes, and copy again. A successful export message
only proves that the clipboard held a syntactically valid graph, so semantic
contracts must also confirm the expected current function and links. This
avoids accidentally validating a stale but valid earlier copy.

Before `Ctrl+A` in a Blueprint graph, click verified empty canvas space. If a
pasted selection or node still owns focus, Unreal may copy only that selection
and omit the native function entry even though `Ctrl+A` was sent. The SaveGame
slot-reader acceptance caught this as an 18-node export instead of 19. The
required cycle is: click empty canvas, select all, copy, assert function name and
exact node/pin counts, and assert the reciprocal native-entry execution link.

When locating a node block in generated `.eddgraph` text, anchor the search to
its `Begin Object Class=...` line. Searching only for a linked pin or function
name can match an unrelated node that merely references the target. The
SaveGame adapter generator now anchors Branch, DynamicCast, and VariableGet
blocks by their concrete serialized node classes.

Treat numeric defaults semantically rather than matching one textual spelling.
UE 5.6 can round-trip an authored `3.0` as `3.000000`. Validators should parse
the serialized scalar, compare it within a strict tolerance, and still require
the pin to be unlinked when the default is meant to drive execution.

Serialized `DefaultValue` checks must also anchor the property name exactly.
Never search for the substring `DefaultValue=`, because it also occurs inside
`AutogeneratedDefaultValue=` and can make a contract accept an unauthored pin
default. The recovery-selection contracts match the comma-delimited
`DefaultValue="..."` property itself.

For a multi-function recovery slice, export every empty target first and require
exactly one native entry node before pasting anything. Install and validate each
body independently, then run the complete live set before compile. After
compile/save, reopen and export every function again and rerun the same suite.
Only the post-compile exports become canonical `live-snippets`; this caught
missed root drags while keeping an in-memory visual impression from becoming
evidence.

Use `tools/unreal/Invoke-EnhancedEditorInput.ps1` for the narrow editor-input
seam instead of rebuilding inline `user32` calls. It requires the exact editor
window handle and supports focused SendKeys, client-coordinate clicks, drags,
and wheel zoom. Visual coordinates remain provisional: after every root-pin
drag, export the complete graph and require a reciprocal native-entry link.

Blueprint Assist may insert `K2Node_Knot` reroutes into a dense graph while it
is active. Before compiling a newly installed dense function, export it and
require the exact expected node count plus zero knots, then activate a small
stable function such as `EnterDroneMode`. After compile/save, reopen and export
the dense function again and repeat both checks. If knots have already been
injected, replace the whole non-entry body from the deterministic paste artifact
instead of attempting a fragile manual knot cleanup.

Do not use fixed My Blueprint/search coordinates after the saved Blueprint
layout changes. On the current Client Director layout, those coordinates can
focus the graph canvas and type the query as a comment node. Open functions
through `tools/unreal/Open-BlueprintFunctionViaFindResults.ps1`, which focuses
the persistent Find Results field, explicitly presses Enter, and opens the
exact result. If a coordinate attempt ever mutates the graph, undo immediately
and require the original exact node count plus the executable contract before
continuing.

Use `tools/unreal/Move-SelectedBlueprintNode.ps1` for finicky native-entry
placement. Give it the exported start coordinates, grid-aligned target, and an
`ExpectedNodeMarker` when possible. It exports the selected node after every
bounded drag, rejects non-converging or off-grid movement, and catches selection
transfer caused by overlap. Always move an entry into empty graph space before
connecting it; do not traverse the dense calculation body.

Enhanced can ignore a drag synthesized only by repeatedly changing the absolute
cursor position, even though the foreground window and coordinates are correct.
`Invoke-BlueprintRelativeDrag.ps1` holds the requested mouse button and emits raw
relative MOVE deltas; `Move-SelectedBlueprintNode.ps1` uses it for movement and
then proves the selected node's exact serialized coordinates. A successful
input call alone is never evidence that a node moved or that pins connected.

At minimum zoom after `Home`, a native function entry and the first pasted body
node can occupy the same screen region. Treat that as an export-and-relocate
problem, not a reason to retry pin drags. Export the graph, clear selection,
select the native entry through an unobstructed header area, move it with the
bounded node mover, and require the serialized coordinates to change. Only then
drag between freshly measured pin positions. Re-export before compile and again
after compile/save; both exact contracts must pass, and only the post-compile
export may be promoted to `live-snippets`.

The Enhanced mod root may contain DevKit-managed `Content`, `Shared`, and
`KitContent` directories beside authored `Local`. Repository synchronization is
deliberately allowlisted to `Local/**/*.{uasset,umap,ubulk,uexp}` and root
`modinfo.json`; never recursively ingest every recognized extension beneath the
whole mod root, or a mirrored `KitContent` tree can recursively duplicate the
project.

Enhanced's pure string-normalization node is
`KismetStringLibrary.Trim(SourceString) -> ReturnValue`. The harvested native
form is `repository-string-trim-node-form.eddgraph`. Use it for persisted
identifier validation; an ID is accepted only when it is non-empty and exactly
equal to its trimmed form.

For object-targeted nodes that do not appear in an empty graph's action menu,
add or reuse a member with the exact object type, drag a getter into the graph,
then drag from that typed output and search for the property/function. This is
how the accepted `SG_EDD_RepositoryStorage.RepositorySchemaVersion` getter and
setter were harvested. Frame the graph (`Home`) and re-check the pin position
before every drag; canvas panning invalidates remembered coordinates.

Disposable Blueprint probes can remain rooted by the editor transaction buffer
or copied-node clipboard through `GCObjectReferencer`. Closing their asset
editor, dropping Python references, and collecting garbage may still be
insufficient. Never force-delete the package file from beneath a live editor.
Guarded-quit, relaunch without opening the probe, delete immediately through
`EditorAssetLibrary`, and verify both the API marker and physical package
absence before closing again.

## Document-sync runtime gate

Run `tools/unreal/Validate-DocumentSyncPIE.py` once from the editor console, then
start PIE three times in response to its markers:

1. The first PIE captures two production waypoints and ends after
   `SECOND_PIE_REQUIRED:True`.
2. The second constructs a normal component with an authored surviving segment
   and ends after `THIRD_PIE_REQUIRED:True`.
3. The third constructs a normal component with one deliberately mismatched
   authoritative channel and ends at `AUTOMATIC_RESULT:PASS`.

Do not save the editor package after this gate. The harness restores and verifies
every class default, but setting those defaults temporarily still marks the
Blueprint package dirty. Close the editor, choose Don't Save, and require
`LogExit: Exiting.` The accepted production asset is the already compiled/saved
asset from before the test. A pass is valid only when the log also contains
`PRESERVED_AUTHORED_SEGMENT_VALID:True`,
`INVALID_INPUT_ROLLBACK_VALID:True`, and `CLASS_DEFAULTS_RESTORED:True`.
