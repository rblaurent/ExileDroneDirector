# Continuation Handoff

Last updated: 2026-08-14 at the frozen offline dolly-zoom contract checkpoint

This is the first file a fresh implementation session should read. It is a
high-signal continuation map, not a replacement for the authoritative evidence
in `implementation-plan.md`, `devkit-findings.md`, and
`blueprint-workflow.md`.

## Non-negotiable scope

- Continue backend implementation through automated/debug dogfood first, then
  use the proven dogfood findings to implement the polished UI.
- Do not start cook, Workshop, G-Portal, deployment, or release work.
- Prove behavior end to end. Generated graph shape alone is not acceptance.
- Automate a finicky editor operation before repeating it manually.
- Commit and push every clean feature checkpoint.
- Never claim that the whole mod is complete.
- The next accepted product gate is full debug/keyboard dogfooding after the
  complete backend. Polished UI follows dogfood; cook and release do not.

## Repository and clean starting state

- Repository: `T:\Projects\ExileDroneDirector`
- Branch: `main`
- Current live acceptance started from remote-equal `6c66099`, with the
  accepted focus helper and frozen diagnostic boundary described below; HEAD must
  equal `origin/main` before checkpoint work is committed
- Expected state at this checkpoint: clean worktree and remote-equal `main`
- Git remote: `origin/main`
- Enhanced DevKit root: `F:\CEUE5Devkit`
- No Enhanced editor is intentionally open at this checkpoint. Never start a
  second instance if a later seam opens one.

Re-establish state before editing:

```powershell
Set-Location T:\Projects\ExileDroneDirector
git status --short
git rev-parse HEAD
git rev-parse origin/main
Get-Process UnrealEditor,ConanSandbox -ErrorAction SilentlyContinue
```

If the hashes differ, inspect history and the working tree. Do not reset user
work. Read these documents in order:

1. `docs/continuation-handoff.md`
2. `docs/implementation-plan.md`, especially section 1.1 and ordered task 9
3. the tail of `docs/devkit-findings.md`
4. `docs/blueprint-workflow.md` before any live installation

## What is genuinely accepted

The server repository backend is accepted through private-by-default creation,
owner-only load/save/list/delete, publish/unpublish, public discovery, immutable
published fetch, private deep clone with source attribution, A/B SaveGame
persistence, restart/recovery, optimistic revisions, and typed failures.

The trajectory backend is live-accepted through scalar/vector/quaternion and
adaptive-arc primitives, position/orientation compilation and absolute-time
evaluation, combined cinematic pose, five flight profiles and C2 smoothing,
stateless airframe/gimbal solving, angular-rate-limited fixed-step prebake, and
complete desired-airframe stream composition. The source-sampling bridge that
feeds that accepted desired stream is also live-accepted end to end.

The prior desired-stream live acceptance is `8d8b603`:

- nine desired-stream graphs contain 30, 218, 104, 104, 104, 94, 84, 37, and
  8 nodes
- exact precompile and postcompile contracts pass
- two warm runs and one independent fresh NullRHI run pass
- each runtime passes 15 forward and 15 reverse compilations, all five profiles,
  invalid families, direct boundaries, immutable inputs, and restoration
- a separate cold process loads all nine core assets and compiles all six
  Blueprints with zero errors
- live/mirror Client Director SHA-256 is
  `E36634647AEFE2DD8C206D10EAE1F66154545B2C03539171BF152E79DA8D688F`

Do not weaken or replace those helpers. Compose them.

## Accepted source-sampling bridge state

Implementation commit `0e31940` live-accepts compiled-source sampling into the
accepted desired stream. It samples position, distinct authored body
orientation, distinct authored gimbal orientation, and all ten smoothed
flight-profile values on one exact absolute-time schedule.

Seven offline checkpoints were pushed after `8d8b603` before live acceptance:

### `2aa201f` — reference and schema

- `tools/trajectory/airframe_source_sampling_reference.py`
- `tools/trajectory/test_airframe_source_sampling_reference.py`
- `tools/trajectory/airframe_source_sampling_blueprint_schema.json`
- `tools/trajectory/test_airframe_source_sampling_blueprint_schema.py`

Reference execution covers exact/partial schedules, distinct body/gimbal,
all five profiles, timeline divergence, invalid steps, physical rejection,
immutable inputs, and 40 seeded forward/reverse cases.

The schema freezes 22 variables and seven functions:

1. `ResetAirframeSourceSamplingV1`
2. `ValidateAirframeSourceSamplingInputsV1`
3. `CompileAirframeSourcePositionProfilesV1`
4. `BuildAirframeSourcePositionBodyProfileSamplesV1`
5. `BuildAirframeSourceGimbalSamplesV1`
6. `CommitAirframeSourceSamplesToDesiredV1`
7. `CompileAirframeSourceSamplingV1`

### `f5fc0da` — reset and input validation

- reset: 34 full / 33 paste nodes
- validation: 43 full / 42 paste nodes
- reset executes poisoned state, invalidates desired/prebake first, clears
  exactly thirteen candidates and six scalars, and preserves authored inputs
- validation executes 103 valid and 15 invalid exported-link cases
- both generators are byte deterministic and full-scaffold owned

### `33267f6` — position/profile component compilation

- `CompileAirframeSourcePositionProfilesV1`: 44 full / 43 paste nodes
- stages the derived segment count
- calls `CompilePositionRouteV1`, then `CompileFlightProfilesV1`
- requires aligned component publications
- derives `ceil(total / step) + 1` with partial-terminal handling
- validates 2..65,536 samples before publishing total/count/validity
- executes 105 valid schedules, false-stage no-op, and eight failure families in
  both forms
- complete scaffold passed in 94.4 seconds

### `6d0ce52` — position/body/profile source sampling

- `BuildAirframeSourcePositionBodyProfileSamplesV1`: 130 full / 129 paste nodes
- clears only its twelve owned candidate arrays before the stage guard
- loads distinct body authorship plus common durations into the accepted
  orientation compiler and proves exact duration/start/total alignment
- samples `min(index * fixedStep, total)` and requires exact position/body
  segment, local-alpha, completion, and validity agreement
- evaluates the accepted smoothed profile at that same coordinate and appends
  position, body, and all ten profile values only after complete helper success
- executes 44 exact/partial/all-profile/seeded schedules in both orders,
  poisoned repeats, immutable sources, timeline corruption, and injected
  compile/evaluator/profile failures in both forms
- failures retain only a bounded aligned twelve-channel private prefix
- complete scaffold passed in 93.5 seconds

### `d63a377` — distinct gimbal source sampling

- `BuildAirframeSourceGimbalSamplesV1`: 80 full / 79 paste nodes
- clears only the gimbal candidate and never references the completed twelve
  position/body/profile candidates
- replaces the shared orientation cache from distinct gimbal authorship, then
  re-proves every compiled duration/start and the exact total
- samples the published absolute schedule and requires exact position/gimbal
  validity, segment, local-alpha, and completion agreement before each append
- executes 44 exact/partial/all-profile/seeded schedules in both orders,
  poisoned repeats, protected upstream state, timeline corruption, and injected
  evaluator failures in both forms
- complete scaffold passed in 91.9 seconds

### `5052ee4` — atomic source-to-desired commit

- `CommitAirframeSourceSamplesToDesiredV1`: 84 full / 83 paste nodes
- invalidates only source validity before preflight
- requires exact 2..65,536 cardinality across all thirteen arrays and equality
  to the published expected sample count
- copies all thirteen arrays plus total and step only after complete preflight
- invokes the accepted desired compiler and publishes source validity last only
  after both desired and prebake validity are true
- executes 44 oracle-valid handoffs, sixteen direct preflight failures with
  downstream object-identity preservation, and desired/prebake failures
- complete scaffold passed in 90.5 seconds

### `7a97958` — policy-free top-level orchestration

- `CompileAirframeSourceSamplingV1`: 7 full / 6 paste nodes
- exact six-call order: reset, validate, compile components/schedule, sample
  position/body/profiles, sample distinct gimbal, commit desired stream
- owns no state, branch, loop, reroute, alternate path, or external link
- complete scaffold passed in 91.1 seconds

### `0e31940` — live Enhanced acceptance

- `Configure-AirframeSourceSamplingAssembly.py` idempotently owns all 22 typed
  variables and seven functions on Client Director.
- The installed full graphs contain 34, 43, 44, 130, 80, 84, and 7 nodes in
  reset-to-orchestration order. Every exact contract passed before compile and
  again on the checked-in postcompile exports.
- Two warm CDO runs and one independent fresh NullRHI run each pass 10 forward
  and 10 reverse compilations, exact and partial schedules, all five profiles,
  six invalid families, two direct boundary cases, poisoned state, immutable
  inputs, and exact restoration of the complete 325-property schema union.
- Distinct authored body and gimbal rotations remain distinct in source
  candidates and accepted desired outputs. No single-rotation alias was added.
- Guarded shutdown reached `LogExit: Exiting.`. Closed-editor preview reported
  16 unchanged packages and exactly Client Director changed; sync copied one.
- Live and mirrored Client Director SHA-256 is
  `EA2576672F41F56474DB3BE9CA529264273CF94F0DABFC5CB7671CFAE596DF35`.
- A fresh cold commandlet loaded all nine core assets, compiled all six
  Blueprints, emitted `EDD_COLD_LOAD|RESULT|PASS`, and exited with zero errors.
- The complete scaffold with mirrored MVP assets passes in 96.3 seconds and now
  owns all seven live exports, the configurator, and the runtime harness.

## Live compiled-document adapter state

The normalized compiled-document-to-source boundary and downstream diagnostics
are live-accepted. The five saved graphs are reset 24 nodes, validation 114,
atomic source commit 30, diagnostics 149, and orchestration 5. Their exact
postcompile exports are scaffold-owned.

### Document-adapter evidence

- `2e0cc75` freezes the independent reference, v2 normalized parallel-array
  schema, explicit legacy mismatch, and diagnostic contract. Seven reference
  tests, six schema tests, and 20 seeded forward/reverse cases pass. The v1
  `CameraTransform` rotation is rejected; body and gimbal authorship remain
  separate required quaternion channels.
- `112ae23` adds deterministic reset full/paste graphs. The subsequently
  tightened ownership contract adds one adapter-owned exact-duration
  accumulator plus four diagnostic-local scratch values, so reset is now 24
  full / 23 paste nodes and clears them without touching any normalized
  authored input.
- The current validation checkpoint adds a deterministic 114 full / 113 paste
  graph. It fail-closes schema/engine versions, all eleven array shapes, the
  2..512 waypoint bound, fixed-step and document-duration domains, positive
  unique IDs, ordered segment adjacency, finite positive segment durations,
  and exact accumulated duration. Its interpreter passes 80 seeded valid
  documents and 16 injected failure classes in both forms.
- The current commit checkpoint adds a deterministic 30 full / 29 paste graph.
  It copies exactly nine accepted inputs only after adapter validation, uses
  different getters for body and gimbal quaternions, invokes the already
  accepted source compiler once, and publishes adapter validity last only when
  source, desired, and prebake validity all hold. Forty seeded distinct-track
  handoffs plus stage/source/desired/prebake failure cases pass in both forms.
- The current diagnostic checkpoint adds a deterministic 149 full / 148 paste
  graph. It emits six aligned arrays for internal waypoint IDs, accepted
  position velocity/acceleration jumps, separately authored body/gimbal
  angular-rate jumps, and threshold flags. Four guarded quaternion-log calls
  read three body keys and three gimbal keys independently; failures only
  invalidate diagnostic-local state. Sixty seeded compiled documents match the
  independent reference in both forms, including mixed spatial curves and
  loose/tight warning thresholds. No authoritative motion state is writable.
- The final offline graph is a deterministic 5 full / 4 paste coordinator. It
  calls reset, validation, commit, and diagnostics in that exact order and owns
  no policy or state. Focused contracts prove the complete call chain executes
  even when an earlier stage fails, leaving fail-closed state to the owning
  stage rather than inventing an alternate orchestration path.
- The initial warm run caught two real missing native-entry wires in validation
  and diagnostics. Those saved graphs were repaired, and contracts now require
  the native entry seam for every non-orchestrator graph so the defect cannot
  regress behind a structurally complete body.
- Two repaired warm runs each pass 10 forward plus 10 reverse valid documents,
  six invalid families, three diagnostic policies, one direct boundary case,
  immutable inputs, complete union restoration, and separate body/gimbal values.
- A fresh editor's real PIE world passed on the player-owned Client Director:
  distinct authorship, diagnostic waypoint ID 107, end-to-end valid publication,
  input immutability, restored defaults, and clean PIE teardown.
- Guarded shutdown reached `LogExit: Exiting.`. Sync copied only Client Director;
  live and mirror SHA-256 are
  `6D6F964EFDA4D63BD7FE09F13077926AB2859A1F9B787D08CA8DC5DD08836A98`.
- Fresh cold load passes with zero errors. The complete scaffold passes in
  103.3 seconds and validates generated full/paste forms plus all five saved
  live exports.

## Live camera scalar-track engine state

The common absolute-time scalar engine for lens, focus, and bounded effect
channels is now live-accepted on Client Director. Its nine saved graphs are
reset 25 nodes, validation 138, candidate construction 20, atomic commit 29,
compile orchestration 5, result reset 13, sample publication 78, selected-
segment evaluation 124, and top-level evaluation 40. Exact postcompile exports
are checked in and scaffold-owned.

### Camera scalar evidence

- All nine native entry seams and complete generated bodies pass one unified
  postcompile export audit. The interpreters cover 80 valid tracks plus nine
  validation failure classes, 40 candidate tracks in both domains, atomic
  commit and seven failure classes, 161 publication samples plus eight
  fail-closed cases, 50 segment samples across every mode/domain combination,
  and 288 forward/reverse top-level queries plus four failures.
- Live installation exposed two Enhanced clipboard importer gaps. It silently
  discarded `Max_IntInt`, and separately discarded `Max_DoubleDouble` plus
  `Min_DoubleDouble`. Validation now uses a typed `Select` for the safe previous
  index; output clamping uses comparisons plus typed `Select` nodes. Contracts
  forbid the dropped calls and prove equivalent numeric behavior.
- The Find Results automation now repeats result activation before any canvas
  mutation. Exact-count audits found and removed every stale cross-paste before
  the asset was allowed to compile or save.
- Two warm runtime runs each pass 10 forward and 10 reverse tracks, 121 total
  queries, all five interpolation modes, linear and reciprocal optical domains,
  seven invalid families, immutable inputs, and exact default restoration.
- PIE on the real player-controller-owned Client Director passes reciprocal
  optical interpolation: authored 100/400 distance endpoints evaluate to the
  expected 160 midpoint at alpha 0.5. The game-world result, input immutability,
  default restoration, and automatic teardown all pass.
- Guarded shutdown reached `LogExit: Exiting.`. Closed-editor preview reported
  16 unchanged packages and exactly Client Director changed; sync copied one.
  Live and mirrored Client Director SHA-256 is
  `BE81A999B4E5729CBC83C1D18166BDCFF33ED6ECF3FED7F8C6036926E2CC38A7`.
- An independent fresh NullRHI runtime repeats the full 121-query acceptance.
  A separate cold commandlet loads all nine core assets and compiles all six
  Blueprints with zero errors. The complete scaffold with mirrored MVP assets
  passes in 106.3 seconds and owns deterministic full/paste generation plus all
  nine saved live exports.

This accepts the reusable backend math and execution engine. It does not yet
claim channel-owned lens/focus/effect storage, camera modes, event targets,
debug controls, attended dogfood, or polished UI.

## Live camera channel-assembly state

The lens/focus/effect ownership boundary is now frozen offline in
`camera_channel_assembly_reference.py` and
`camera_channel_assembly_blueprint_schema.json`. It defines one discrete
filmback snapshot and thirteen independently authored scalar channels: focal
length, aperture, focus distance, focus influence, exposure, and eight bounded
effect weights. Focus distance alone may use reciprocal optical interpolation;
no key array or compiled slice is shared between channels.

Sparse channels expand at compile time into explicit constant tracks spanning
the complete shot duration. Compilation builds a separate flattened candidate
bank and atomically replaces the prior compiled bank only after all thirteen
channels succeed. Evaluation stages committed slices into the accepted generic
scalar engine without recompiling, evaluates every channel at one absolute
time, and publishes a complete frame only after all samples succeed. Filmback
remains discrete and carries a stable preset ID plus resolved positive sensor
dimensions.

Seven reference tests and four schema tests pass, including reciprocal 100/400
focus producing a 160 midpoint, independent bounded effects, zero-duration
shots, invalid filmback/domain/range rejection, failed-recompile snapshot
preservation, and history-free forward/reverse scrubbing. The complete scaffold
passes with 1,472 output lines in 108.5 seconds. This checkpoint is offline
only: no channel assembly variables or functions have yet been installed in
Client Director.

`ResetCameraChannelCompileV1` is the first deterministic assembly graph at 33
full / 32 paste nodes. It clears exactly the eight candidate arrays and three
frame-result arrays, resets compile/evaluation scratch and validity, preserves
all authored input, and—critically—does not touch the last accepted compiled
bank. Both forms pass exact ownership and execution contracts and are now owned
by the complete scaffold. Next: validate the flattened authored bank, its
filmback snapshot, channel uniqueness, gap-free slices, domains, and policies.

`ValidateCameraChannelInputsV1` follows at 126 full / 125 paste nodes. It
accepts zero to thirteen sparse authored channels; proves supported unique IDs,
gap-free disjoint key slices, exact flattened cardinalities, 1..512 keys per
authored channel, finite non-negative duration, and a resolved positive
filmback. Non-focus channels must be linear; focus distance alone may be linear
or reciprocal. Both graph forms pass 81 seeded valid banks and 17 failure
families without touching candidate or compiled storage. Next: expand sparse
defaults and compile/copy each canonical channel into the private candidate
bank through the accepted scalar engine.

`CompileCameraChannelCandidateV1` is deterministic at 186 full / 185 paste
nodes. For one canonical channel index it selects the fixed physical policy,
copies an authored disjoint slice or builds the correct one/two-key sparse
default, invokes the accepted scalar compiler exactly once on one mutually
exclusive path, and appends the successful compiled snapshot to private flat
storage. Three path-local copy pipelines avoid unsafe Blueprint exec merges.
Both forms match 40 complete thirteen-channel oracle banks, including sparse
defaults and reciprocal focus, while an invalid authored channel preserves the
prior candidate prefix. Next: atomic whole-bank commit after exact thirteen-
channel preflight.

`CommitCameraChannelAssemblyV1` is deterministic at 71 full / 70 paste nodes.
It independently proves exactly thirteen disjoint candidate slices, exact five-
array cardinality, domain cardinality, and 1..512 keys per channel before one
synchronous publication chain copies the bank, duration, and filmback snapshot.
Validity is the final write. Both forms pass varied atomic success plus twelve
stage/shape/offset/count failures, each preserving the prior compiled snapshot.
Next: the top-level reset/validate/thirteen-channel compile/commit coordinator.

`CompileCameraChannelAssemblyV1` completes offline assembly compilation at 11
full / 10 paste nodes. It is a policy-free reset -> validate -> bounded 0..12
candidate loop -> guarded commit coordinator. Both forms prove the exact order,
storage non-ownership, validation short-circuit, and late candidate failure
short-circuit. Next: deterministic result reset, committed-slice staging,
per-channel scalar publication, and the complete absolute-time evaluator.

`ResetCameraChannelResultV1` is deterministic at 15 full / 14 paste nodes. It
clears only the three outgoing value/velocity/acceleration arrays, filmback
frame output, completion/validity, and evaluator indices/guard. The compiled
bank, compile validity/failure code, authored inputs, and query time are absent
from the graph and proven preserved in both forms. Next: stage one committed
channel slice into generic scalar evaluation scratch without recompilation.

`StageCompiledCameraChannelV1` is deterministic at 119 full / 118 paste nodes.
It bounds-checks one canonical disjoint slice and domain, copies the five
compiled arrays into generic scalar evaluation scratch, and stages the fixed
physical/bounds policy. It never reads authored keys, calls the compiler, or
writes the packed compiled bank. Both forms match 520 independently staged
channels across five absolute queries each and reject sixteen poisoned
metadata/slice/domain/index cases. Next: evaluate that staged channel and append
its scalar sample to the assembly result arrays.

`PublishCameraChannelSampleV1` is deterministic at 25 full / 24 paste nodes.
It forwards the one assembly query into the staged scalar evaluator, requires a
valid scalar result, appends value/velocity/acceleration in lockstep, and folds
completion across canonical channels. Invalid evaluation sets the assembly
stage false and cannot append or touch compiled/authored storage. Both forms
pass exact call, ownership, append-order, completion, and failure contracts.
Next: the final reset/stage/publish loop and filmback/validity-last frame
publication.

`EvaluateCameraChannelAssemblyV1` completes the offline nine-graph family at 40
full / 39 paste nodes. It resets, rejects non-finite queries or an invalid
compiled bank, loops canonical channel indices 0..12 through stage and publish,
requires exactly thirteen successful lockstep samples, then publishes the
compiled filmback and frame validity last. Both forms match 840 forward plus
reverse oracle frames and reject six query/compile/slice/domain/cardinality
failures. All nine graphs now have deterministic full/paste snippets, exact
structural/semantic interpreters, and complete scaffold ownership. Next: prepare
one-editor configuration, live runtime, real-world PIE, save/sync, cold-load,
and full regression tooling before opening Unreal.

The complete nine-graph family is now installed, compiled, saved, synchronized,
and accepted on Client Director. The saved full graphs contain 33, 126, 186,
71, 11, 15, 119, 25, and 40 nodes in reset-to-evaluation order. Exact native-
entry and executable contracts pass on every postcompile export, and all nine
live captures are scaffold-owned.

Live installation found one real importer defect before save: 18 validation
string comparisons and two staging comparisons were discarded because their
generated call nodes named `KismetMathLibrary` instead of
`KismetStringLibrary`. Both generators now emit the correct library, focused
contracts require the library and exact call counts, and every non-orchestrator
contract requires its native entry seam. The malformed validation body was
cleared back to its native entry and reinstalled from the corrected generator;
no incomplete graph was compiled or saved.

Two warm runtime runs each pass 21 assembly compilations, 121 frame evaluations,
six invalid families, forward/reverse history-free queries, reciprocal-focus
midpoint 160 for authored 100/400 distances, independent bloom, immutable
authored inputs, failed-recompile snapshot preservation, and exact default
restoration. PIE on `/Game/Dev/AlmostEmpty` passes the same critical optical,
filmback, thirteen-channel, and independent-effect frame on the real player-
controller-owned Client Director, then restores defaults and tears down.

Guarded shutdown reached `LogExit: Exiting.`. Closed-editor review found exactly
Client Director changed; sync copied that one package and reverse preview reports
17 unchanged packages. Live and mirror SHA-256 are both
`5A4E8E6E6538DE3526BA72BC68D94DC1FC654C57ED51C0874226C3A5CAE4E655`.
An independent fresh NullRHI run repeats the 21/121/six-family matrix. A fresh
cold commandlet loads all nine core assets and compiles all six Blueprints with
zero errors. The complete scaffold with mirrored MVP assets passes in 119.6
seconds and owns all nine generated full/paste forms plus all nine saved live
exports.

This accepts camera-track compilation and synchronized frame evaluation. The
next backend seam is the engine-application boundary: explicitly discover and
freeze supported Cine Camera/post-process properties, apply a valid compiled
frame transactionally, report unavailable properties rather than pretending
success, and restore the viewer's prior camera state. Then continue with manual
and target focus helpers, dolly zoom, comfort overrides, Directed / Free Look /
Carrier Freecam modes, bounded event adapters, debug dogfood, and polished UI.

## Offline camera engine-application state

The engine-neutral application/restoration architecture is frozen in
`camera_engine_application_reference.py` and
`camera_engine_application_blueprint_schema.json`. It maps the discrete
filmback dimensions plus all thirteen evaluated channels into fifteen unique
canonical targets; no camera channel is reused or collapsed. Filmback width and
height, focal length, aperture, and manual focus distance are required engine
capabilities. Optional post-process/look targets are explicitly availability-
gated.

Application is a preflighted transaction. Engine version, manifest identity,
canonical capability shape, frame shape/order/ranges, camera session, and every
unavailable target are checked before the first property write. An unavailable
optional target is safe to skip only when its desired logical value is neutral;
there is no concrete engine field to inspect or mutate. Otherwise the entire
frame rejects as unavailable without partial mutation. This prevents false
success without inventing viewer state for a feature Enhanced does not expose.

One active session captures exact scalar baselines plus complete native
Filmback, FocusSettings, and PostProcessSettings structs once.
Repeated begin cannot overwrite that baseline or swap capability manifests.
Restore returns every scalar and complete native struct exactly, is stable when repeated,
and remains mandatory before camera ownership is released. Seven reference and
seven schema tests pass, including full support, safe neutral skips, missing core
properties, active unavailable rejection, poisoned frame rollback, repeated
capture, exact restoration, and seeded forward/reverse application. The
complete scaffold owns the four new files. Next: generate and interpret the
engine-neutral reset/validation/staging graphs and a deterministic read-only
property probe before opening the editor.

`ResetCameraEngineApplicationResultV1` is the first deterministic graph at 7
full / 6 paste nodes. It clears only unavailable-target diagnostics, failure and
result state, plus two per-call scratch scalars. Capability identity, normalized
input, captured scalar/native-struct baselines, current applied state, session
activity, and applied-frame count are absent from the graph and proven to retain
object identity under poisoned execution. Full/paste SHA-256 is
`FE8D00786C2F0B2B03880AAA452C4FDC6CCA6525A3CAB8A93B0DEF48B7487FA8` /
`C7A4449A711CF6D0E1894EB5E4C4515F3EF7D5C934A5F3B7E9FDF33D386AA23B`.
Next: stage the accepted fifteen-value frame without touching engine state.

`StageEvaluatedCameraChannelFrameV1` is deterministic at 58 full / 57 paste
nodes. It invalidates and clears prior adapter input first, requires a valid
thirteen-value evaluated channel frame plus a finite positive filmback and
nonempty preset ID, then appends width, height, and each canonical channel index
0..12 exactly once. Input validity publishes last. Eight failure families leave
an empty invalid adapter input, while 80 seeded frames preserve the source and
map exactly. Capability, baseline/current, active-session, authored, candidate,
and compiled storage is absent. Full/paste SHA-256 is
`39C4C9FCF5BF1BFDC2651FFF2D4255F6611F3EFFAE442BEAEA22C0CF4542438C` /
`A39EA6AD24B5B2C80C5CF09876FAE84C194AFA501AF1A82F7D7210F123C0C4F2`.
Next: validate the frozen capability manifest and all fifteen staged values
before any engine capture or write.

The non-persistent property-discovery package is frozen offline before any
editor launch. `camera_engine_property_candidates_v1.json` declares exact,
unique candidate paths and override partners in the same fifteen-target order;
`camera_engine_property_probe_reference.py` resolves only readable,
same-value-writable, exactly typed candidates and hashes a canonical engine-
versioned manifest; `Probe-CameraEngineProperties.py` spawns one transient mod
camera, observes only those declared paths, and destroys it in `finally` without
any asset-save API. Five targets deliberately have no direct candidate—focus
influence, grading, tint, sharpening, and matte—so they cannot silently alias a
nearby property. Seven probe contracts pass, including override-partner loss,
wrong/missing core types, observation-order-independent identity, path-alias
rejection, and non-persistent script structure. Next: the fifteen-value and
capability validation graph, then run the probe in the first single editor.

`ValidateCameraEngineApplicationInputsV1` is deterministic at 171 full / 170
paste nodes. It fail-closes staged validity, nonempty engine/manifest/filmback
identity, exact 15-value and 15-capability shapes, all five mandatory capability
bits, finiteness, positive filmback dimensions, and every accepted physical/
normalized channel range. It does not inspect optional current-state neutrality;
that check correctly remains after baseline capture and immediately before
engine writes. Both graph forms pass 80 seeded valid inputs and 56 failure
families. Baseline/current/session state, camera references, engine properties,
and all authored/candidate/compiled banks are absent. Full/paste SHA-256 is
`025A054997EDAC4CF5C9D9D0D6FD44F3B3801EEE6830FA2D4BF64EB183AA7CC0` /
`8E74F36320E5D8C04E34C6F82EED611848E1A97C15C3B211B6FB0262C6745D0A`.
The engine-neutral preflight set is complete. Next: open one editor, run the
non-persistent property probe, review/freeze the actual manifest, then generate
the concrete capture/apply/restore helpers against only proven paths.

The single Enhanced 5.6.1 editor then ran the transient probe twice against the
real `BP_EDD_DroneCamera` Cine Camera component. Both runs produced identical
manifest ID
`0425CCF862121F06C64732519AF40703C2AC73104B3FA10A3E065F914E1FB26E`,
reported no missing required target, and destroyed the transient actor. The
checked-in manifest marks filmback width/height, focal length, aperture, manual
focus, exposure, bloom, vignette, motion blur, and scene fringe available; focus
influence, grading, tint, sharpening, and matte remain unavailable. Every
available post-process value has its exact writable Boolean override partner.
The validation graph now requires the exact engine build string and manifest ID
rather than merely nonempty identity. Next: derive concrete Blueprint node forms
for the proven paths, then generate capture, apply, and restore offline before
installing anything.

The follow-up live node-form probe is also complete and fully cleaned from the
Blueprint. Enhanced compiled exact native getters and setters for Filmback,
FocusSettings, PostProcessSettings, CurrentFocalLength, and CurrentAperture,
plus Break/Set Members forms for the three native structs. The harvested forms
are now deterministic repository templates with a structural regression test;
no production engine-application graph was installed or saved at this point.

One important contract correction is explicit before production generation:
Enhanced serializes exposed post-process Set Members fields with implicit
override ownership and does not expose readable `bOverride_*` output pins.
Therefore exact session restoration will capture and restore the complete
native Filmback, FocusSettings, and PostProcessSettings structs. Logical arrays
may describe adapter ownership and diagnostics, but they must not pretend to be
an exact read-back of hidden engine override bits. The next checkpoint must
update the reference/schema around this stronger whole-struct baseline before
generating capture, apply, restore, and the thin orchestrator.

That correction is now frozen offline. The reference represents all three
native structs explicitly, preserves unrelated opaque fields during supported
member updates, and restores the original snapshots exactly. The Blueprint ABI
removes the misleading baseline/current override arrays and instead owns three
native baseline variables plus three same-typed apply scratch variables. Seven
reference and seven schema tests pass. Existing reset/stage/validation graphs
remain valid because they never touched the replaced state. Next: deterministic
capture, apply, restore, and thin orchestrator generators/interpreters.

The concrete offline family is now complete. `CaptureCameraEngineStateV1` is
41/40 full/paste nodes and performs only native reads; it preserves an active
baseline and captures all opaque struct fields. `ApplyCameraEngineFrameV1` is
60/59 nodes, requires an active session, valid staged input, valid camera, and
neutral values for all five unavailable logical targets before its first
engine write; it changes only the ten manifest-supported targets and preserves
unrelated fields in all three structs. `RestoreCameraEngineStateV1` is 28/27
nodes and writes the captured Filmback, FocusSettings, and PostProcessSettings
structs whole, plus exact focal/aperture scalars; inactive repetition is a no-op
and failed preflight is zero-write/retryable. The nine/eight-node
`ApplyEvaluatedCameraChannelFrameV1` coordinator owns no values or policy and
short-circuits validation and capture failures. All four generators are byte-
deterministic, both forms pass structural and executable interpreters, and the
complete scaffold passes in 139.2 seconds and owns their sixteen
generator/test/snippet files. Next: commit/push, then configure and install the full seven-
graph family in the one existing editor for compile/runtime/PIE/cold acceptance.

## Live-accepted camera engine application

The complete seven-graph family is installed, compiled, saved, mirrored,
frozen as postcompile exports, and accepted through engine-neutral runtime,
real native PIE mutation/restoration, fresh process, and cold load.

- Saved graphs are reset 7 nodes, stage 58, validation 171, capture 41, apply
  60, restore 28, and orchestration 9. Every exact full-graph contract passed
  before compile and again on the checked-in postcompile exports.
- The first real compile correctly rejected three native component getters
  that still claimed director self-ownership. No bad compile was saved. The
  capture/apply/restore generators now externalize `DroneCamera` with explicit
  `BP_EDD_DroneCamera_C` ownership, their contracts reject `bSelfContext=True`,
  and the three live bodies were replaced from the corrected deterministic
  snippets.
- The corrected compile produced no Blueprint compiler messages between the
  fresh compile markers and Unreal displayed the green compile indicator.
  Saving then returned true.
- Guarded shutdown reached `LogExit: Exiting.`. Closed-editor reverse preview
  reported 16 unchanged packages and exactly Client Director changed; sync
  copied one package.
- Live and mirrored Client Director SHA-256 is
  `C4D9AE3CE312D4305C46E41CC1033FD4B653F5D23B124178CE27F923D4CDE1C5`.
- The scaffold owns the configurator, explicit cross-Blueprint component
  contract, generators, snippets, and all seven live exports. The complete
  repository regression with mirrored MVP assets passes in 113.1 seconds.

- Two warm CDO runs in both frame orders pass canonical staging, exact manifest
  validation, camera-less fail-closed capture, inactive restoration, immutable
  channel results, and complete default restoration. A separate fresh NullRHI
  process repeats those engine-neutral checks and exits successfully.
- Native actor references cannot legally be assigned to a class default or to
  this non-instance-editable Blueprint variable from Unreal Python. The
  validator preserves that engine ownership boundary rather than bypassing it;
  real writes execute only on the player-owned component in PIE.
- Three sequential real PIE worlds pass: one forward frame, one reverse frame,
  and one unsupported focus-influence request. Each valid world applies its
  frame twice, produces exact supported native values and implicit override
  ownership, increments the frame count, preserves the first baseline across a
  repeated capture, restores the complete Filmback/Focus/PostProcess structs
  plus focal length/aperture exactly, and makes repeated restore a no-op.
- The unsupported request returns `application_preflight_failed`, performs zero
  native writes, and does not increment the applied-frame count. All three
  scenarios preserve the eight evaluated channel-result properties, exit Drone
  Mode, restore CDO defaults, and tear PIE down automatically.
- Guarded shutdown closed every asset editor and reached `LogExit: Exiting.`.
  Closed-editor preview and sync both reported all 17 packages unchanged.
  Live and mirrored Client Director remain byte-identical at SHA-256
  `C4D9AE3CE312D4305C46E41CC1033FD4B653F5D23B124178CE27F923D4CDE1C5`.
- Fresh cold load opens all nine core assets and compiles all six Blueprints
  with zero errors. The complete scaffold, including deterministic regeneration,
  full/paste interpreters, all seven postcompile exports, and validator ownership,
  passes in 114.7 seconds.

This accepts the camera engine-application boundary. Next: preserve it while
implementing the remaining Phase 5 camera helpers, Directed / Free Look /
Carrier Freecam modes, and bounded authorized event adapters toward debug
dogfood.

The first remaining focus-helper boundary is now frozen offline. A normalized
Set Focus Here hit atomically replaces one fixed world marker while a trace miss
is zero mutation. Manual distance, fixed marker, rack between two fixed targets,
prebaked actor tracking, and smoothed autofocus all compile physical focus
distance onto the already accepted absolute-time schedule; reciprocal rack
focus retains the accepted optical-domain behavior. Stateful autofocus exists
only during chronological compilation, never during query evaluation. Mode-
specific inputs are mutually exclusive, transient actor pointers cannot cross
the boundary, and the helper can publish only `focus_distance_cm`—never focus
influence, another camera channel, engine state, or motion authorship. Eight
reference tests, six schema tests, forty seeded cases, immutable-input checks,
and eight failure families pass. Next: deterministic reset and Set Focus Here
graphs, then validation/build/commit/orchestration before one-editor acceptance.

The first two focus graphs are now deterministic and scaffold-owned. Compile
reset is 6 full / 5 paste nodes: it clears only private candidate distances,
invalidates candidate/compile results, clears the failure code, and preserves
every authored input, trace/marker value, and the complete prior compiled focus
snapshot. `SetCameraFocusHereV1` is 9 full / 8 paste nodes and remains outside
the compile coordinator: trace validity is its sole execution guard, the miss
path has no marker write, and a hit commits exact impact position, marker
validity, and incremented revision in that order. Full/paste executable
contracts and byte-identical repeated generation pass; the complete scaffold
passes in 115.0 seconds. Next: focus input validation.

`ValidateCameraFocusInputsV1` is now deterministic at 78 full / 77 paste
nodes. It fail-closes the private candidate-valid flag, accepts only the five
frozen modes and two focus domains, bounds the schedule to 2..65,536 samples,
requires the camera-position count to match, and enforces mutually exclusive
mode-specific source cardinality plus the smoothed-autofocus response domain.
It cannot read trace/marker state, prior compiled focus, engine application,
documents, or motion authorship. Per-sample finite time/geometry/distance and
rack-range checks deliberately remain with candidate construction immediately
before each append. Both graph forms pass 80 seeded valid banks and twelve
failure families; byte-identical regeneration and the complete scaffold pass
in 115.2 seconds. Next: candidate construction.

`BuildCameraFocusDistanceCandidatesV1` is now deterministic at 332 full / 331
paste nodes. Five exclusive bounded lanes walk the accepted absolute schedule,
so inactive mode arrays are never read. Every lane checks finite exact time,
strict ordering, camera geometry, and its mode-owned source immediately before
append. Manual, fixed-world, prebaked tracking, linear/reciprocal fixed-target
rack, and chronological exponential autofocus all produce physical centimetre
distances. Failure publishes no validity and leaves at most a private bounded
prefix; success is published only when the built count equals the input count.
Both graph forms match the reference across 80 seeded mode/domain cases and
reject eleven poisoned per-sample families without mutating authored inputs;
the complete repository scaffold passes in 115.8 seconds.
Next: atomic focus-channel commit, then the tiny compile coordinator.

`CommitCameraFocusDistanceChannelV1` is now deterministic at 37 full / 36
paste nodes. It invalidates the result before preflight, preserves the prior
compiled snapshot on every failure, rechecks candidate stage, bounded equal
cardinality, and exact mode/domain identity, then value-copies times, distances,
mode, and domain before publishing validity last. Eighty seeded snapshots and
six direct failure families pass in both graph forms; the complete repository
scaffold passes in 116.2 seconds. Next: the tiny compile
coordinator, followed by one-editor acceptance for the complete focus helper.

`CompileCameraFocusDistanceChannelV1` completes the focus helper's offline
compile family at 5 full / 4 paste nodes. It contains only the exact ordered
reset, validate, build, and commit self-calls; it owns no variables, branches,
loops, or policy. All six focus functions now have deterministic full/paste
snippets and executable contracts. The complete repository scaffold passes in
116.4 seconds. Next: one-editor
configure/paste/entry-wire repair/compile/save/runtime/PIE/cold
acceptance for the whole focus helper before any later camera mode work.

The focus-helper live-acceptance package was prepared while Unreal was closed.
The schema now freezes every scalar/vector default; the idempotent configurator
owns exactly 24 variables and six function seams; the runtime validator covers
both query orders, every mode/domain, Set Here hit/miss, full-compile failure,
direct-commit failure, immutable inputs, and complete default restoration. The
PIE validator repeats reciprocal rack, Set Here, and fail-closed snapshot
preservation on the real player-owned Client Director and owns automatic PIE
teardown. Offline live-tool contracts and the complete repository scaffold pass
in 116.2 seconds.

The complete camera focus helper is now live-accepted in Enhanced 5.6.1. The
six cold-editor exports contain 6, 9, 78, 332, 37, and 5 nodes (467 total) with
zero reroute knots and pass the exact reset, Set Here, validation, candidate,
commit, and orchestration contracts. Unreal compile/save succeeds. Runtime
execution passes ten mode/domain cases in forward and reverse order, Set Here
miss/hit, invalid full compile, invalid direct commit, immutable inputs, and
default restoration. Three automatic PIE worlds pass reciprocal rack focus at
160 cm, Set Here miss, Set Here hit, and prior-snapshot preservation on the
real player-owned Client Director; PIE exits automatically.

PIE class-default probes must be followed immediately by
`Restore-CameraFocusHelperSchemaDefaults.py`. Enhanced can persist temporary
Blueprint-owned defaults across class reinstancing even after an in-memory CDO
restore. The restore tool compiles first, reacquires the current generated
class, converges all 24 variables to the frozen schema, saves, and verifies.
The subsequent idempotent configurator reports all eight array defaults at
count zero. Never compile this Blueprint from inside a Slate post-tick callback
after PIE teardown: that rejected experiment crashed in the Python plugin. A
fresh editor then cold-loaded and compiled all nine core assets, proving the
persisted package remained clean. Final live exports are scaffold-owned under
`tools/blueprint/live-snippets`.
Guarded shutdown reached `LogExit: Exiting.`; reverse sync copied only Client
Director, and live/mirror packages are both 20,628,898 bytes with SHA-256
`F0458A4C426DFF2DE4BD34E357F5A76D7D76A2B58C19E180FB23D19BC0D95635`.

Next: continue task 10 with the remaining Phase 5 camera helpersâ€”focal-plane /
depth-of-field debug diagnostics, dolly-zoom authoring, verified effect/look
helpers, and local comfort overridesâ€”before Directed / Free Look / Carrier
Freecam playback modes and bounded authorized event adapters.

The focal-plane / depth-of-field diagnostic boundary is now frozen offline.
It reads only one complete evaluated 13-channel camera frame and its filmback,
then publishes circle of confusion, hyperfocal distance, focal plane, bounded
near/far limits, front/rear depth, and focal-plane size. The thin-lens model
uses filmback diagonal / 1500 for approximate circle of confusion. An
unbounded far limit is a Boolean plus zero scalar sentinelâ€”never infinity or an
arbitrary huge distance. Six executable reference tests include exact full-
frame math, hyperfocal transition, aperture behavior, immutable input, invalid
families, and 80 seeded forward/reverse evaluations. Four schema tests freeze
18 scalar variables, four ordered functions, complete-frame staging, atomic
publication, and diagnostic-only ownership. Next: deterministic reset, stage,
compute, and tiny evaluation graphs before one-editor acceptance.

The first two DOF graphs are now deterministic and scaffold-owned. Reset is 19
full / 18 paste nodes and clears all six stage plus twelve result fields in one
unconditional chain. Complete-frame staging is 100 full / 99 paste nodes: it
invalidates and clears its owned stage first, requires upstream frame validity,
exactly thirteen finite channel values, and finite positive filmback dimensions,
then copies only filmback plus canonical focal/aperture/focus indices and
publishes stage validity last. Eighty seeded frames and nine corruption families
pass in both forms; generation is byte-identical. Next: physical DOF
calculation, then the tiny evaluator coordinator.

The physical DOF calculation is now deterministic at 90 full / 89 paste nodes.
It revalidates all six staged inputs, implements the frozen filmback-diagonal
circle of confusion and thin-lens near/far equations, publishes an explicit
bounded/unbounded far state, and sets result validity last on both terminal
paths. The executable interpreter matches the independent reference across 80
seeded camera states (seven bounded, 73 unbounded) and rejects ten invalid or
physically impossible stages while preserving prior unpublished diagnostics.
The graph reads only the six DOF stage scalars and cannot touch camera-channel,
focus, airframe, document, transform, or engine state. Next: the tiny
reset/stage/compute evaluator coordinator, then one-editor acceptance of all
four graphs.

The offline DOF family is complete. `EvaluateCameraDofDiagnosticsV1` is four
full / three paste nodes and contains only the exact ordered calls reset →
stage → compute. It owns no variables, policy, branch, loop, reroute, or hidden
alternate path; compute is terminal. Both forms and deterministic regeneration
are scaffold-owned. Next: prepare the idempotent configurator, runtime oracle,
and automatic PIE probe while Unreal is closed, then install and accept the
four-graph family in one editor.

The DOF live-acceptance package is prepared while Unreal remains closed.
`Configure-CameraDofDiagnostics.py` idempotently owns exactly 18 scalar
variables and four functions. The runtime validator compares six bounded and
unbounded optical frames in forward and reverse order to the independent
reference, proves upstream frame immutability, and covers direct-compute plus
invalid-frame failures. The automatic PIE validator exercises bounded,
unbounded, and fail-closed frames on the real player-owned Client Director and
tears down every PIE session itself. The separate post-PIE restore compiles
outside the callback, reacquires the generated class, and restores both the 18
DOF defaults and the four accepted upstream camera-frame defaults temporarily
used by the probe. Next: one-editor configure/paste/compile/save/runtime/PIE/
restore/cold acceptance and final live exports.

The focal-plane / approximate depth-of-field diagnostic is now live-accepted.
The four saved graphs contain 19, 100, 90, and 4 nodes in reset/stage/compute/
evaluate order, and fresh postcompile exports pass their exact structural and
executable contracts. Live runtime matches the independent thin-lens oracle for
six camera frames in forward and reverse order, covers both bounded and
unbounded far depth, preserves the evaluated camera frame, and passes direct-
compute plus invalid-frame failures. Three automatic PIE worlds pass bounded,
unbounded, and fail-closed scenarios on the real player-owned Client Director.
The separate post-PIE restore compiles outside the callback and verifies all 18
DOF plus four staged upstream defaults before an idempotent configurator rerun.
Guarded quit reached `LogExit: Exiting.`; reverse sync copied only Client
Director. Live/mirror packages are both 21,167,373 bytes with SHA-256
`E7DFEBF802DC5B26278838445BBFF0C6C9818C47919DD903E7B7E551646F9120`.
A fresh NullRHI commandlet loaded all nine core assets, compiled all six
Blueprints, emitted `EDD_COLD_LOAD|RESULT|PASS`, and exited with zero errors.
The four cold-editor exports are scaffold-owned under
`tools/blueprint/live-snippets`. Next: continue Phase 5 with deterministic
dolly-zoom authoring before comfort/effect helpers and playback modes.

The dolly-zoom authoring boundary is now frozen offline. It accepts an explicit
time schedule, separately authored camera positions, one fixed subject, a
reference sample index, and a reference focal length. It derives focal length
with `focal / subject-distance` held constant, assuming the independent gimbal
or look-at author keeps the optical axis on that subject. It cannot write
position, body, gimbal, focus, compiled camera-channel, engine, document, or
playback state. Validation and bounded candidate construction have distinct
validity flags; reset preserves the prior compiled snapshot; commit replaces
the whole aligned result and publishes validity last. Derived focal lengths
outside 1..1000 mm reject the result instead of being clamped, because clamping
would break framing. Five executable reference tests cover exact optics,
immutability, twelve failure cases, and 80 seeded forward/reverse routes; four
schema tests freeze 15 variables and the ordered reset, validate, build, commit,
and compile family. Next: generate and interpret those five Blueprint graphs in
order before opening Unreal.

`ResetCameraDollyZoomV1` is now deterministic at nine full / eight paste nodes.
It unconditionally clears the two private candidate arrays, invalidates input
validation, candidate publication, and compilation, and clears the failure code.
Exact ownership tests prove the five inputs and four-field prior compiled lens
snapshot are never referenced. Both forms and byte-identical regeneration are
owned by the complete scaffold. Next: input validation.

`ValidateCameraDollyZoomInputsV1` is now deterministic at 29 full / 28 paste
nodes. It checks the complete schedule/position shape, 2..65,536 sample bound,
reference index, and finite 1..1000 mm reference lens value, then publishes its
dedicated validation flag last. It reads exactly four inputs, writes only the
validation flag and failure code, and cannot touch the fixed subject, candidate,
compiled, movement, orientation, engine, document, or playback state. Eighty
seeded valid cases and ten failure families pass in both graph forms. Next:
bounded subject-distance and focal candidate construction.

`BuildCameraDollyZoomCandidatesV1` is now deterministic at 106 full / 105 paste
nodes. One bounded loop verifies the fixed subject, reference and per-sample
camera vectors, absolute timeline, minimum one-centimetre subject distance, and
the unclamped 1..1000 mm derived lens domain. Each accepted sample appends one
distance and one focal value; a failure breaks with an aligned bounded prefix,
and candidate validity is published only when both lengths equal the full input
count. The graph matches the independent oracle across 80 seeded routes and 11
failure families in both forms, including spatial reversal, and cannot reference
compiled data, body/gimbal authorship, engine, document, or playback state.
Next: atomic whole-result commit.

`CommitCameraDollyZoomV1` is now deterministic at 31 full / 30 paste nodes. It
rechecks candidate validity, all three aligned array lengths, sample bounds, and
the reference index before touching the accepted snapshot. Failure invalidates
the result but preserves all four prior compiled fields. Success copies times,
subject distances, focal lengths, and the exact indexed reference distance as a
whole transaction, clears failure, and publishes validity last. Eighty snapshot
cases and eight poisoned preflights pass in both forms. Next: the tiny ordered
compile coordinator.

## Next ordered implementation

Continue through the remaining Phase 5 camera helpers, Directed / Free Look / Carrier Freecam modes,
and bounded event adapters with authorization. After the complete backend,
expose temporary debug controls and logs, run attended dogfood, and only then
implement the polished UI.

The first task-10 seam is now live-accepted from the frozen contracts in
`camera_scalar_track_reference.py` and
`camera_scalar_track_blueprint_schema.json`. It provides hold, linear, smooth,
cinematic, and explicit-Hermite presets; value/velocity/acceleration output;
linear physical units; reciprocal-distance optical focus; and bounded output
without authored-key mutation. Eight reference and four schema tests pass. The
next checkpoint is channel-owned lens/focus/effect storage and composition.

`ResetCameraScalarTrackCompileV1` is the first deterministic graph checkpoint:
25 full / 24 paste nodes. It clears exactly the five generic candidate arrays,
invalidates compile/evaluation results and scratch, preserves every authored
input plus query time, and is byte-deterministic and scaffold-owned.

`ValidateCameraScalarTrackInputsV1` follows at 138 full / 137 paste nodes. It
enforces exact array shape, ordered absolute time and endpoints, finite values,
declared ranges, linear/reciprocal domains, all five modes, and explicit tangent
ownership. Its interpreter passes 80 seeded valid tracks and eight failure
classes in both forms. The next graph is candidate conversion/publication.

`BuildCameraScalarTrackCandidatesV1` is now 20 full / 19 paste nodes. It copies
the four validated structural arrays, converts values once into linear or
reciprocal optical space, remains private, and cannot publish compile/evaluation
validity. Forty seeded tracks pass in both domains and graph forms; invalid-stage
execution is a no-op. Next: atomic commit, then absolute-time evaluation.

`CommitCameraScalarTrackV1` is 29 full / 28 paste nodes and publishes validity
only after exact five-array cardinality preflight. `CompileCameraScalarTrackV1`
is the policy-free 5 full / 4 paste reset→validate→build→commit coordinator.
Both are deterministic and scaffold-owned. Next: absolute-time evaluation.

The absolute-time evaluator is now frozen as three ownership-safe helpers plus
one top-level query function. A result-only reset clears stale samples; a
selected-segment helper composes the already accepted time-profile and quintic
math; and one publication helper exclusively owns reciprocal-focus derivative
conversion, output bounds, and validity-last publication. This explicit split
avoids competing Blueprint execution merges while keeping all interpolation
paths history-free. The scalar reference and amended nine-stage schema pass.
Next: generate and interpret the result-reset graph, then publication, segment,
and top-level evaluation in that order before opening the editor.

`ResetCameraScalarTrackResultV1` is now deterministic at 13 full / 12 paste
nodes. It clears exactly seven public sample fields and five evaluator-scratch
fields, while preserving the compiled snapshot, authored inputs and policies,
compile result/failure code, and query time. Both graph forms pass exact
ownership/execution interpreters, and the complete scaffold passes in 103.2
seconds. Next: the single optical/bounds publication helper.

The reciprocal compiler guard is hardened before publication: physical values
below `5.562684646268003e-309` now fail validation because their inverse cannot
fit in a finite double. The Python compiler independently enforces the same
boundary and checks its converted result. Validation remains 138 full / 137
paste nodes and now passes 80 valid tracks plus nine failure classes in both
forms. The complete scaffold passes in 103.3 seconds. No normal focus, linear
channel, interpolation, or authored-bound behavior changed.

`PublishCameraScalarTrackSampleV1` is now deterministic at 78 full / 77 paste
nodes. It invalidates first, guards compiled and staged state, converts linear
or reciprocal-domain value/velocity/acceleration with safe denominators,
applies optional min/max policy without mutating keys, zeroes derivatives only
when a clamp actually binds, and publishes validity last. Full and paste
interpreters match 161 seeded samples and reject eight poisoned cases without
overwriting stale values. The complete scaffold passes in 103.1 seconds. Next:
the selected-segment interpolation helper.

`EvaluateCameraScalarTrackSegmentV1` is now deterministic at 124 full / 123
paste nodes. It validates the staged segment, publishes segment coordinates,
implements hold explicitly, uses the accepted time-profile helper for preset
blend values with exact local derivative polynomials, and maps cubic Hermite
endpoint tangents through the accepted quintic helper. Each of its three paths
stages one complete domain sample and calls the sole publisher; there is no exec
merge. Full and paste interpreters match 50 mode/domain samples and five failure
cases. The complete scaffold passes in 102.6 seconds. Next: top-level absolute-
time selection, including constant tracks and history-free forward/reverse
queries.

`EvaluateCameraScalarTrackV1` completes the offline scalar engine at 40 full /
39 paste nodes. It resets first, rejects non-finite queries, handles constant
tracks, marks completion correctly at zero duration, selects the first matching
right boundary with one bounded loop, defaults beyond-duration queries to the
last segment, and delegates interpolation. Both forms pass 288 forward plus
reverse absolute-time queries and four fail-closed cases. All nine scalar
graphs are deterministic, interpreter-owned, and scaffold-owned; the complete
repository suite passes in 105.7 seconds. Next: one-editor configure/paste/
entry-wire repair/compile/save/runtime/PIE/cold acceptance for the full scalar
family before channel-owned lens/focus/effect storage.

The one-editor acceptance tooling is prepared and syntax-checked while the
editor is closed: `Configure-CameraScalarTrackAssembly.py` idempotently owns all
32 variables and nine functions; `Validate-CameraScalarTrackRuntime.py` covers
forward/reverse live compilation, every preset/domain, absolute queries,
failure families, immutable inputs, and restoration; and
`Validate-CameraScalarTrackPIE.py` checks reciprocal-focus output on the real
player-owned Client Director and tears PIE down. Next: run that package in one
editor and freeze exact postcompile exports.

## Critical design mismatch

The Python document model has distinct `body_rotation` and `gimbal_rotation`,
but the current Blueprint v1 document/waypoint bridge exposes one
`CameraTransform` rotation. Do not alias that rotation into both source arrays.
The accepted adapter resolves this by requiring separate v2 quaternion channels
and rejecting the lossy legacy source. A future migration may decode distinct
canonical fields, but must never manufacture both from `CameraTransform`.

## Hazards already paid for

- Enhanced reflects the double minimum as `FMin`, not `Min_DoubleDouble`; the
  latter can silently disappear during paste.
- Native exports may omit textual zero defaults for linked int/real/bool pins.
  Infer only those typed empty defaults in contract interpreters.
- Generic getters can retain the wrong container. A new fixed-step getter first
  inherited `ContainerType=Array`; the fixed generator and contract explicitly
  require `ContainerType=None`. Retarget every pin type/container.
- Never run two DevKit editors. File locking caused Client Director save failure.
- Do not kill Unreal as a save strategy. Use guarded quit and confirm clean exit.
- Tiny-angle rates are sensitive to engine quaternion representation. Do not
  hide this with a wider pose tolerance; compare poses, prove rate bounds, then
  replay the accepted prebake Blueprint exactly.
- Desired-stream success stage index is the terminal sample index, not an
  orchestration stage number.
- Late top-level desired failure may leave bounded private scratch prefixes, but
  desired/prebake validity and authoritative publication are false after reset.
- Direct desired commit preflight preserves an already accepted downstream
  snapshot while invalidating desired validity; that narrower helper contract is
  intentional.

## Standard commands

```powershell
# Focused document-adapter reference/schema
python tools\trajectory\test_compiled_document_source_adapter_reference.py
python tools\trajectory\test_compiled_document_source_adapter_blueprint_schema.py

# Complete repository proof
.\tools\Test-Scaffold.ps1 -RequireMvpAssets

# Cold proof after live save and shutdown
.\tools\Test-ColdAssetLoad.ps1

# Before commit
git status --short
git diff --check
git diff --stat

# After push: require equality
git rev-parse HEAD
git rev-parse origin/main
```

## Confidence statement

Confidence is high in every live checkpoint explicitly accepted above, including the
complete live source-sampling bridge, lossless compiled-document adapter with
post-boundary discontinuity diagnostics, scalar-track engine, and synchronized
thirteen-channel lens/focus/effect frame assembly, and exact transactional
engine property application/restoration. Confidence is not yet claimed for
camera modes, events, keyboard
dogfood, UI, cooking, Workshop, G-Portal, deployment, or whole-mod completion.
