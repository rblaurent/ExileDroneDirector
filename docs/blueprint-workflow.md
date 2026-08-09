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
- Runtime state machines live in named Blueprint functions or components, not a
  monolithic Event Graph.
- PIE evidence is recorded in `docs/devkit-findings.md` before a diagnostic node
  is removed or generalized.
- A graph screenshot is supporting evidence only. Checked-in node serialization
  proves links; compile/save proves asset validity; PIE proves runtime behavior.
- Snippet execution inputs must be intentionally internal or intentionally
  unlinked and documented as public caller entry points. Dangling external links
  are rejected.
- Camera work never moves the player character. The verified SpectatorPawn
  backend caches `OriginalPawnRef`, temporarily possesses the drone, and restores
  the cached pawn (or calls `UnPossess` when none existed) before exit completes.
- Possession is a tested runtime resource, not an incidental side effect: every
  entry/exit graph must state and validate its cache/restore contract.

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
8. Six-axis input accumulation. **First translation slice proven in PIE: W/S,
   D/A, and E/Q feed forced local forward/right/up movement, W/D/E produced the
   expected displacement, and exit/re-entry restored and reacquired possession.
   Mouse look plus precision/boost scaling remain pending.**

Each snippet is captured only after its live-editor version compiles and passes
its focused PIE check.
