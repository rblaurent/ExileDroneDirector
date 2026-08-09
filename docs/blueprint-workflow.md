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
- Never hand-edit `NodeGuid`, `PinId`, or `LinkedTo` relationships casually.
- Do not paste a snippet twice unless it is explicitly designed to be repeated.
- Compile after every paste; do not accumulate multiple unverified graph batches.
- If a paste intentionally excludes an existing function-entry node, reconnect
  that entry in the live graph and export the complete graph again. A one-sided
  serialized external link can compile green while leaving the function body
  unreachable; the checked-in contract must require both reciprocal exec links.
- Runtime state machines live in named Blueprint functions or components, not a
  monolithic Event Graph.
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
12. Atomic waypoint capture. **The named `CaptureCurrentWaypoint` function
    appends ID, transform, focal length, aperture, focus distance, and hold time
    to six lockstep draft arrays, then advances `NextWaypointId`. Its complete
    24-node/86-pin graph round-tripped through Unreal, compiled green, and is
    guarded internally by a valid typed drone reference. The client EventGraph
    polls `K` with `WasInputKeyJustPressed` only after owner, active-mode,
    camera-validity, speed, translation, rotation, and roll processing. Two
    direct runtime function calls in deterministic two-player PIE produced IDs
    `[1,2]`, equal channel lengths, exact transforms and lens values, zero
    remote-client draft mutation, no leaked drone, and exact view restoration.
    The character-creation widget consumed synthetic keyboard injection, so one
    physical `K` acceptance press after completing character creation remains a
    deliberately separate hands-on gate; the serialized K-edge topology is
    enforced offline.**

Each snippet is captured only after its live-editor version compiles and passes
its focused PIE check.
