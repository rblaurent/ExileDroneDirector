# Continuation Handoff

Last updated: 2026-08-15 after carrier-frame transport-sample checkpoint

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
- Current checkpoint is deterministic twist-minimizing carrier-frame quaternion
  transport described below; after the checkpoint push, HEAD must equal
  `origin/main` before atomic compiled-track commit work starts
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

The complete five-graph dolly-zoom family is now offline-green. The final
`CompileCameraDollyZoomV1` graph is five full / four paste nodes and contains
only reset -> validate -> build -> commit, with no variable, branch, loop,
reroute, or hidden policy. All five graph pairs regenerate byte-identically and
are structurally plus executably owned by the complete scaffold. Next: prepare
the idempotent one-editor configurator, runtime oracle, automatic PIE probe, and
separate post-PIE schema restore while Unreal remains closed.

The dolly-zoom live-acceptance package is now prepared while Unreal remains
closed. The configurator idempotently owns exactly 15 variables and five
functions. Runtime checks six physical routes in forward and reverse order,
whole-input immutability, explicit body/gimbal compiled-track immutability, full
compile rejection, and direct commit rejection. Three automatic PIE sessions
exercise shrinking, expanding, and fail-closed behavior on the real player-owned
Client Director and tear down themselves. The separate restore compiles before
reacquiring the generated class and converges all schema defaults outside the
Slate callback. Next: one-editor configure/paste/compile/save/runtime/PIE/
restore/cold acceptance and final live exports.

The dolly-zoom helper is now live-accepted in Enhanced 5.6.1. The five saved
graphs contain 9, 29, 106, 31, and 5 nodes. Unreal initially discarded the four
internal execution links in the validation body while preserving every data
link and the manually connected native entry seam; the offline shape/oracle
contract therefore produced a false green. The four links were repaired before
save, and the scaffold now compares every live node/pin topology against the
deterministic full graph in addition to requiring resolved reciprocal links.
Final live exports pass that exact round-trip check. Runtime passes six physical
routes in forward and reverse order, two fail-closed families, immutable inputs,
and explicit preservation of distinct body/gimbal quaternion and angular-rate
tracks. Three automatic PIE worlds pass shrinking focal values 100/50/25,
expanding values 25/50/100, and invalid-input snapshot preservation on the real
player-owned component. Defaults restore, the configurator is idempotent,
guarded shutdown reaches `LogExit: Exiting.`, and reverse sync copies only Client
Director. Live and mirror are both 21,599,167 bytes with SHA-256
`CF31350826811204EAFD9CEC74E4B474EB09318A9F8472067DCB5CD4F012FBFF`.
A fresh NullRHI cold load compiles all six Blueprints with zero errors and emits
`EDD_COLD_LOAD|RESULT|PASS`. The five live exports are scaffold-owned. Next:
verified effect/look helpers and local comfort overrides, then the documented
camera modes and bounded event adapters before debug dogfood.

The named base-look boundary is now frozen offline. Eight exact presets—Raw,
Clean Cinematic, Epic Landscape, Dreamy Shallow Focus, Dark Sorcery, High-Speed
FPV, Vintage Lens, and Documentary—each expand to all thirteen canonical camera
channels. The result publishes the preset ID, channel IDs, complete base values,
complete effective values, and one authored-override bit per channel, so a preset
cannot hide its numbers. Sparse individual authorship wins only for the matching
channel and input order cannot affect the canonical output. Channels without an
accepted Enhanced 5.6.1 direct mapping remain at their exact neutral defaults in
the v1 catalog rather than pretending an unavailable visual effect worked. The
helper owns only new `CameraLook*` state and cannot mutate or alias the accepted
camera-channel bank, engine application, document, body, gimbal, playback, or
local comfort policy. Eight executable reference tests, including 80 seeded
forward/reverse compositions and eleven failure families, plus five schema tests
pass. Next: generate the six reset, validate, base-build, authored-overlay,
atomic-commit, and coordinator graphs offline before reopening Unreal.

`ResetCameraLookCompositionV1` is now deterministic at 13 full / 12 paste
nodes. It clears exactly the three private candidate arrays, invalidates
validation/candidate/result publication, clears failure, and converges the two
scratch scalars. Every authored input and all five fields of the prior accepted
look snapshot are structurally absent and retain object identity in the reset
interpreter. The full and paste forms regenerate byte-identically, require the
complete reciprocal execution chain, and are scaffold-owned. Next: exact preset,
shape, uniqueness, finiteness, and per-channel bounds validation.

`ValidateCameraLookInputsV1` is now deterministic at 91 full / 90 paste nodes.
It accepts exactly the eight frozen presets, requires aligned override arrays
with at most thirteen entries, and rejects unknown or duplicate channels plus
non-finite or out-of-bound values. Eighty-eight valid requests and thirteen
failure families pass the executable interpreter; both forms have exact
reciprocal links and byte-identical regeneration. It writes only validation,
failure, and private scratch state, so candidates and the last accepted camera
look remain untouched. Next: explicit thirteen-value base preset expansion.

`BuildCameraLookBaseValuesV1` is now deterministic at 136 full / 135 paste
nodes. After validation it rebuilds the private base array from empty and maps
each of the eight preset names through an explicit thirteen-append execution
chain: 104 literal values are visible in the graph, including exact neutral
values for unavailable direct mappings. The interpreter verifies every preset
against the reference catalog; false validation remains a no-publication path.
Both forms have exact reciprocal links and byte-identical regeneration. Next:
apply sparse authored overrides in canonical channel order.

`ApplyCameraLookAuthoredOverridesV1` is now deterministic at 46 full / 45
paste nodes. A fixed 0..12 loop reconstructs the canonical channel ID, performs
one authored lookup, and appends either that exact authored value or the exact
base value plus the matching Boolean mask. Eighty seeded forward/reverse
compositions prove input order independence and immutable input/base arrays;
false-stage execution publishes nothing. Both forms have exact reciprocal links
and byte-identical regeneration. Next: atomic accepted-result commit.

`CommitCameraLookCompositionV1` is now deterministic at 39 full / 38 paste
nodes. Candidate validity plus exact 13/13/13 base/effective/mask cardinality
guards publication. On success it writes preset identity, rebuilds all thirteen
canonical channel IDs, snapshots the three candidate arrays by value, clears
failure, and publishes result validity last. Eighty randomized snapshots and
five rejected shapes prove success isolation and prior accepted-data
preservation. Both forms have exact reciprocal links and byte-identical
regeneration. Next: the tiny six-stage composition coordinator.

`ComposeCameraLookV1` completes the offline family at 6 full / 5 paste nodes.
It contains exactly five self-calls in the frozen reset -> validate -> base-build
-> authored-override -> atomic-commit order, with no variables, branches, loops,
or hidden camera policy. All six named-look graphs now regenerate
byte-identically, pass their interpreters and exact reciprocal-link checks, and
the complete repository scaffold is green with Unreal still closed. Next:
single-editor install, compile/topology verification, warm runtime routes, PIE
acceptance, guarded shutdown, reverse sync, and cold-load proof.

The named-look helper is now live-accepted. Its six saved native graphs contain
13, 91, 136, 46, 39, and 6 nodes, and their post-compile exports exactly match
the frozen deterministic topology. All eight looks pass forward and reverse in
both the warm editor and a separate fresh NullRHI process; sparse authorship and
all three fail-closed boundaries preserve the prior accepted snapshot, and the
distinct body/gimbal compiled tracks remain untouched. Three automatic PIE
worlds pass Raw, a two-channel authored override, and rejected-input snapshot
preservation on the real player-owned Client Director. The separate restore
proves all 17 defaults, and a repeated configure is a no-op. Guarded shutdown
reached `LogExit: Exiting.`; reverse sync copied only Client Director; all nine
core assets load and all six Blueprints compile with zero errors from cold.
Live/mirror Client Director SHA-256 is
`0ED2F27BE019F43DA05908F32FB10F4F448777CCFA3ADBFD242DC871D5FCB386`.
The complete scaffold, including every frozen live snippet, passes in 135.4
seconds. Next: the separate local comfort layer; it must consume accepted look
output without rewriting named-look authorship.

The viewer-comfort boundary is now frozen offline. It consumes the already
distinct evaluated gimbal plus separate deterministic procedural translation/
rotation offsets and the complete thirteen-channel frame, then publishes one
transient local final-view result. Five continuous 0..1 weights independently
preserve/reduce roll, shake, focus+motion blur, exposure change, and chromatic
aberration; disabled resolves to exact authored behavior but still validates all
inputs/preferences. The other nine camera channels pass through exactly. The
schema owns only 28 `CameraComfort*` variables and six ordered functions and is
structurally unable to accept or publish a body track, rewrite authored/compiled
gimbal data, or touch a Flypath, repository, playback, server, named-look,
camera-channel, or engine-application source. Nine executable reference tests,
including 80 seeded forward/reverse frames and ten rejected families, plus five
schema tests pass. The complete scaffold passes in 132.7 seconds. Next: generate
reset, validation, local-motion, channel-adjustment, atomic-commit, and tiny
coordinator graphs with Unreal closed.

`ResetCameraViewerComfortV1` is deterministic at 14 full / 13 paste nodes. It
clears exactly the two private candidate arrays, resets candidate pose/applied/
validity state plus validation/failure/scratch, and invalidates current result
publication while preserving every source input, all five local preferences,
and the five-field prior accepted result snapshot. Full and paste interpreters
execute poisoned state, exact reciprocal links pass, regeneration is byte-
identical, and the complete scaffold passes in 131.2 seconds. Next: exact
source-pose/quaternion/channel/preference validation.

`ValidateCameraViewerComfortInputsV1` is deterministic at 146 full / 145 paste
nodes. It requires a valid source frame, two finite vectors, two finite unit
quaternions, exact thirteen-channel cardinality and canonical per-index bounds,
plus five finite 0..1 preferences. Eighty seeded frames and ten failure families
pass in both forms; all inputs/preferences remain immutable. It writes only
validation/failure/scratch state, contains one bounded channel loop and no
reroute knots, and structurally excludes candidates, prior results, camera
look/channel/application, document/server/playback, and body/gimbal authorship.
Exact links and byte-identical regeneration pass; the complete scaffold is green
in 132.2 seconds. Next: local motion candidate construction.

`BuildCameraViewerComfortMotionV1` is deterministic at 56 full / 55 paste
nodes. Five Boolean selects resolve disabled policy to exact 1.0 weights. The
graph scales procedural translation, shortest-arc scales procedural rotation,
composes only onto the already evaluated gimbal, reconstructs a vertical-safe
world-level frame from the final forward vector, and blends roll continuously.
It rebuilds the five effective weights and publishes only private candidate
position/gimbal/applied state; body, channels, validity, prior results, and all
external authorship are absent. Eighty forward/reverse oracle cases and a false-
validation no-op pass in both forms. The shake Slerp receives identity from an
explicit zero-Rotator-to-Quat conversion; no by-reference quaternion pin relies
on an ignored literal default. Exact native calls/links and deterministic
regeneration pass; the complete scaffold is green in 135.2 seconds. Next: copy
all thirteen camera values and scale only the four comfort-sensitive outputs.

`BuildCameraViewerComfortChannelsV1` is deterministic at 29 full / 28 paste
nodes. It clears and invalidates the private channel candidate, preflights exact
13 source values plus five effective weights, and performs one bounded loop.
Only focus influence and motion blur use blur weight, exposure EV uses exposure
weight, and chromatic aberration uses its own weight; the other nine values are
exact pass-through. Candidate validity publishes only after all 13 appends.
Eighty forward/reverse oracle frames, disabled/effective-one pass-through, and
three direct failure shapes pass in both forms. Motion candidates, prior result,
external state, and authorship are absent. Exact links/regeneration pass; the
complete scaffold is green in 135.9 seconds. Next: atomic local-result commit.

`CommitCameraViewerComfortV1` is deterministic at 23 full / 22 paste nodes. It
invalidates publication first, rechecks candidate validity plus exact 13/5
channel/weight shape, then snapshots local position, gimbal, values, weights,
and applied flag in one ordered chain; failure clears and validity publishes
last. Eighty accepted deep snapshots and four rejected shapes prove prior local
result preservation in both forms. Inputs/preferences, source families, and all
external state are absent. Exact links and regeneration pass; the complete
scaffold is green in 134.4 seconds. Next: the policy-free five-stage coordinator.

`ApplyCameraViewerComfortV1` completes the offline family at 6 full / 5 paste
nodes. It contains exactly reset -> validation -> local motion -> camera values
-> atomic commit, with no variables, branches, loops, reroutes, or hidden policy.
All six graphs are now deterministic at 14, 146, 56, 29, 23, and 6 full nodes
(274 total); both full and paste forms pass executable contracts and reciprocal
link integrity. The complete repository scaffold is green in 136.4 seconds with
Unreal closed. Next: prepare idempotent configuration, warm runtime oracle,
automatic player-owned PIE, compile-safe restoration, and exact live topology
acceptance tooling before opening one editor.

The complete live-acceptance harness is now frozen while Unreal remains closed.
`Configure-CameraViewerComfort.py` idempotently creates and verifies the exact
28-variable/six-function schema with native Vector and Quat types;
`Restore-CameraViewerComfortSchemaDefaults.py` compiles before reacquiring the
generated class, restores every scalar/array/struct default, verifies it, and
saves. `Validate-CameraViewerComfortRuntime.py` runs eight oracle cases in both
orders, five rejected input families, and a direct malformed commit while
proving immutable inputs, prior accepted snapshot preservation, complete state
restoration, and no writes to body/gimbal, named-look, camera-channel, or
engine-application results. `Validate-CameraViewerComfortPIE.py` owns its Slate
lifecycle and runs three independent sessions on the real player-owned Client
Director: disabled exact behavior, maximum reduction, and fail-closed snapshot
preservation. Static tooling contracts forbid `CameraTransform`, component
mutation, authorship writes, and PIE-time compilation. The complete repository
scaffold owns all five scripts and passes in 137.8 seconds. Next: commit/push
this clean preparedness checkpoint, then open exactly one editor for configure,
six graph installations, exact pre/post-compile export comparison, warm runtime,
three-session PIE, defaults restoration, idempotence, guarded shutdown, reverse
sync, fresh runtime, cold load, and final full regression.

The first one-editor compile exposed and contained a real Enhanced compiler
boundary before any reverse sync: `Quat_Slerp.A` is a native const-reference
input, so its serialized identity literal is ignored and compilation fails when
the pin is unwired. At detection time the project mirror still held the prior
accepted asset. The
motion generator now produces identity through a pure zero-Rotator-to-Quat node
and wires that value into `Slerp.A`; the contract requires both quaternion pins
on every Slerp to be connected. Fresh full/paste generation is byte-identical,
both 80-case interpreters pass, reciprocal integrity is 56 nodes / 79 links,
and the complete scaffold passes in 189.6 seconds.

The viewer-comfort family is now fully live-accepted. Only the rejected motion
body was replaced; all six saved postcompile functions exactly match their
frozen topology at 14, 146, 56, 29, 23, and 6 nodes (274 total), with 13, 195,
79, 38, 24, and 5 reciprocal links. The latest compile/save window contains no
K2, Blueprint, or Python error. Warm runtime passes eight cases in both orders,
five input failures plus malformed direct commit, immutable inputs, accepted-
snapshot preservation, and distinct body/gimbal plus upstream ownership. Three
automatic player-owned PIE sessions pass disabled exact behavior, maximum
reduction, and fail-closed preservation; all defaults restore. Repeated schema
configuration creates nothing and verifies the exact 28 variables / six
functions. Guarded shutdown closes both asset editors and reaches
`LogExit: Exiting.` without assertion. Reverse sync copies only Client Director;
live and mirror SHA-256 are
`DE7D799BAED829FE698609CD259260E55ED97AE423B72BA27D2965719C1E73D8`.
A fresh NullRHI runtime repeats all 22 behavior/failure cases with zero errors;
a separate cold process loads all nine core assets and compiles every Blueprint
with zero errors. The six postcompile exports are now scaffold-owned under
`tools/blueprint/live-snippets`; the complete MVP-required scaffold passes in
134.9 seconds. Next: run the already frozen nine-graph scalar camera engine
through its documented one-editor configure/paste/entry-wire/compile/save/
runtime/PIE/restore/reverse-sync/cold acceptance package.

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

The full scalar family has now been re-accepted on the current integrated
Client Director after the viewer-comfort checkpoint. All nine saved functions
match their deterministic generators at 25, 138, 20, 29, 5, 13, 78, 124, and
40 nodes (472 total) with 639 reciprocal links. Their final postcompile exports
pass exact topology, link-integrity, and executable-oracle checks and replace
the older live captures where Unreal regenerated textual pin metadata.

Acceptance found and fixed a tooling defect rather than a graph defect. Unreal
array properties are live proxy objects; the runtime and PIE validators had
stored those proxies as their cleanup snapshots, so staged test arrays silently
rewrote the alleged originals. Both validators now materialize every schema-
declared array as a plain list and restore all 32 schema fields. A dedicated
read-only validator proves the exact defaults before and after Blueprint
regeneration, and the scaffold statically forbids regression to proxy snapshots.

Warm runtime passes 10 forward plus 10 reverse tracks, 121 absolute-time
queries, and seven invalid families. Real player-owned PIE passes reciprocal
focus at the exact 160 cm midpoint and restores every schema field; all ten
array defaults remain empty after both probes. Guarded shutdown closed both
asset editors and reached `LogExit: Exiting.`. Closed-editor comparison found
only Client Director changed; reverse sync copied exactly that package, and
live/mirror SHA-256 is
`6F2EB7A7812E5974E4E83050B37640AC11916FFF05A31FF461357E28E8CBBB8B`.
A fresh NullRHI runtime repeats the complete matrix, a separate fresh process
proves all 32 defaults across cold Blueprint compilation, and a third process
loads nine core assets and compiles all six Blueprints with zero errors. The
complete MVP-required scaffold passes in 140.1 seconds. Next: continue the
remaining backend camera-mode/event-adapter sequence toward debug dogfood; the
scalar engine is no longer pending.

The first interactive playback-mode boundary is now frozen offline in
`camera_operator_override_reference.py` and
`camera_operator_override_blueprint_schema.json`. It consumes already distinct
authored position, body, and gimbal values plus a fourth, independently
transported carrier-frame quaternion. Body is copied exactly; only the local
final-view gimbal may compose an ephemeral look offset. Carrier-relative input
uses only the separate carrier frame, never body, gimbal, or the lossy legacy
`CameraTransform` rotation.

Directed, Free Look, and Carrier Freecam have explicit state and transitions.
The first accepted frame is exact authored output; return-to-directed and mode
changes preserve offsets and decay them under bounded linear/angular speed and
acceleration; a one-shot Recenter remains latched until exact zero or permitted
new live input cancels it. Free Look smoothly removes inherited carrier
translation, Carrier Freecam supports world or carrier-relative translation,
and the soft tether clamps only the local offset while removing outward radial
velocity. Real local delta time is separate from Flypath/event time, so paused
inspection cannot advance Cues or State Clips. All state is viewer-local and
absent from Flypaths, publication, repositories, and server authority.

Twelve executable reference tests cover exact first-frame and settled Directed
behavior, distinct authorship, all mode transitions, carrier-frame isolation,
tethering, acceleration bounds, recenter/return, deterministic sequences, and
fourteen rejection families. Six schema tests freeze 51 operator-owned variables
and the six-stage reset/validate/translation/look/commit/coordinator ABI. The
complete MVP-required scaffold passes in 134.9 seconds with Unreal closed.
Next: generate and interpret `ResetCameraOperatorOverrideStepV1`, then input
validation, translation integration, look integration, atomic commit, and the
tiny coordinator before any editor work.

`ResetCameraOperatorOverrideStepV1` is now deterministic at 18 full / 17 paste
nodes. Its single execution chain converges exactly seventeen transient fields:
validation, every private candidate, result validity, failure code, and scratch
validity. All eleven inputs, nine policy fields, the complete seven-field
operator state, and every prior accepted result value are structurally absent
and preserve object identity in the executable interpreter. Both forms pass
exact default-value, reciprocal-link, full/paste execution, and byte-identical
regeneration checks; the complete MVP-required scaffold passes in 135.5
seconds. Next: generate the fail-closed input-validation graph.

`ValidateCameraOperatorOverrideInputsV1` is now deterministic at 259 full /
258 paste nodes with 345 / 344 reciprocal links. It invalidates first and reads
only the 24 source, authored-pose, operator-input, policy, and prior-state fields
needed at this boundary. It accepts only the three frozen modes, world/carrier
translation frames, finite bounded controls and delta time, positive bounded
policy values, normalized and finite authored body, authored gimbal, carrier,
and state quaternions, and a canonical zero/identity state when uninitialized.
It writes only validation plus failure code, publishes success last, and cannot
touch candidates, prior accepted results, camera engine state, Flypaths,
repositories, playback/event time, or server authority. Distinct authored body,
gimbal, and carrier-frame getters are structurally required; there is no
`CameraTransform` alias.

Both full and paste forms accept 100 seeded valid sequential frames and reject
all 30 poisoned families while preserving input, policy, and prior-state
snapshots. Regeneration is byte-identical with SHA-256
`14F61F4181F0548542E00B6DA882A38FB068D1AA6B941BA70220395ED0C51419`
for the full form and
`D70D97CDA77E4B087D951A07E6ADCFCF5385012ABBB05CCDEC7E0AC360DD2D72`
for paste. The complete MVP-required scaffold passes in 136.1 seconds with
Unreal closed.

`BuildCameraOperatorTranslationV1` is now deterministic at 105 full / 104
paste nodes with 158 / 157 reciprocal links. It resolves Return to Directed,
maintains the latched Recenter contract, normalizes diagonal input, rotates only
carrier-relative translation through the separate carrier-frame quaternion,
and integrates bounded velocity and offset with acceleration limits. Directed
and Free Look decay inherited translation instead of snapping. Soft tethering
clamps only the local offset and removes only outward radial velocity; the
authored position and both authored rotations are structurally absent. The
first accepted frame always publishes zero local translation, even with queued
input.

The executable oracle exposed a real floating-point edge before editor work:
normalizing the old offset and scaling it is mathematically equivalent to the
reference decay but can round across exact zero one frame earlier. The accepted
graph preserves the reference evaluation order, `offset * (-speed / length)`,
and uses a selected safe denominator only for the already-settled branch. Both
forms match 160 history-explicit forward/reverse candidates plus explicit
world/carrier isolation and false-validation preservation. Full/paste SHA-256
is `A6B5ABF693BF1B671AA72F9D0884F1180F7AA40F473601A69F26B6D0BDC2A95A` /
`EECB8B04B739465886558DE783A22C0CA2B5589FF3B4A4CFFD8A0E980FE22287`.
The complete MVP-required scaffold passes in 138.1 seconds with Unreal closed.

`BuildCameraOperatorLookV1` is now deterministic at 147 full / 146 paste nodes
with 216 / 215 reciprocal links. It integrates a bounded local-axis angular
velocity, constructs the exact axis-angle delta quaternion, composes that delta
only into viewer-local look state, and derives complete candidate position,
body, gimbal, recenter, transition, and override flags. Authored body is a
literal getter-to-setter passthrough. Authored gimbal is returned exactly when
look is identity; only non-identity local look is composed and normalized.
Translation policy, carrier orientation, tether state, authoritative results,
and every external backend are absent.

The graph uses the already-private candidate look quaternion briefly to
materialize the native axis-angle delta through `Quat_SetComponents`. Execution
then freezes angular velocity and final look through setter outputs before any
downstream pure node can re-read the replaced scratch value. Structural
contracts freeze that order. Both forms match 160 history-explicit
forward/reverse frames, including exact body authorship, gimbal-only look,
recenter settlement, transition/override flags, and false-scratch no-op.
Full/paste SHA-256 is
`2B41A5674867E6CADFE6E9118602F415B98C167B42D39AEF8358816C3BC75327` /
`0BA709263311782641D24CB84D63806624A9EB2A11401F1EAC6769054385F172`.
The complete MVP-required scaffold passes in 139.0 seconds with Unreal closed.
Next: atomic commit, then the tiny five-call coordinator before editor work.

`CommitCameraOperatorOverrideV1` is now deterministic at 116 full / 115 paste
nodes with 152 / 151 reciprocal links. It invalidates the result first and
requires validation, translation, and look stages to have succeeded. Incomplete
upstream work preserves the earlier failure and cannot mutate accepted state or
result values. A complete but poisoned candidate fails closed with the stable
`candidate_invalid` code after independently checking the mode, four finite
vectors, and three finite normalized quaternions. Success atomically copies all
seven state fields and all seven result values/flags, clears failure, and
publishes result validity last. Candidate body and gimbal remain separate
getter-to-setter paths; neither can alias the other or `CameraTransform`.

Both forms match 100 complete reference snapshots, reject 11 poisoned candidate
families, and preserve all accepted data across three incomplete-stage cases.
Full/paste SHA-256 is
`644D546EBC6B4AF6569F89329B7A735F29B9338DA9F2F245D8BCCC948FA9BE01` /
`93276321509C905BC936D7B2C66E0BD85496177D10A1CFD0E3789D91C4D6D6C1`.
The complete MVP-required scaffold passes in 139.3 seconds with Unreal closed.
Next: build the tiny reset -> validate -> translation -> look -> commit
coordinator, then accept the complete six-graph family offline before any editor
work.

`ApplyCameraOperatorOverrideV1` completes the offline family at 6 full / 5
paste nodes with exactly reset -> validate -> translation -> look -> commit and
5 / 4 reciprocal execution links. It contains no variables, branches, macros,
reroutes, hidden policy, or alternate terminal. Full and paste contracts freeze
the exact stage identities and order; regeneration is byte-identical with
SHA-256
`6857BC85D589D4827A4018D281DC39544ABC31DE28CCAB42F92CEB76F78C8842` /
`10C90BD9C4D9C10C7FCF82A389525EEED1700381738FD61459171E81838891BB`.

All six operator graphs are now green offline: 651 full nodes with 893
reciprocal links, or 645 paste nodes with 887 links. Their generators,
checked-in snippets, link interpreters, executable oracles, ownership barriers,
and repeat hashes all pass in the complete 138.2-second MVP-required scaffold
with Unreal closed. Distinct authored body and gimbal paths remain structurally
separate across validation, look construction, and atomic publication. Next:
prepare idempotent tooling, then run the documented one-editor configuration,
compile/save/export, warm-runtime, automatic PIE, restoration, and exact
postcompile-topology sequence. Do not open a second editor.

The complete operator live-acceptance harness is now frozen while Unreal remains
closed. `Configure-CameraOperatorOverride.py` idempotently creates and verifies
the exact 51-variable/six-function native Vector/Quat schema, while
`Restore-CameraOperatorOverrideSchemaDefaults.py` compiles before reacquiring
the generated class and restores/verifies every default before saving.
`Validate-CameraOperatorOverrideRuntime.py` prepares 40 history-explicit oracle
frames for both forward and reverse execution, five validation failures, and a
direct poisoned commit. It verifies complete state/result output, exact body
passthrough, separate gimbal/look composition, carrier-frame isolation,
immutable inputs/policy, accepted-snapshot preservation, external ownership,
and cleanup. `Validate-CameraOperatorOverridePIE.py` owns its Slate lifecycle
and three real player-owned sessions: distinct settled Directed authorship,
carrier-relative translation isolated from body/gimbal, and fail-closed state/
result preservation. Static contracts forbid `CameraTransform`, external
authorship writes, component mutation, and PIE-time compilation. The complete
MVP-required scaffold owns all five tools and passes in 139.1 seconds. Next:
commit/push this preparedness checkpoint, then open exactly one editor for the
six graph installations and the complete live acceptance sequence.

The complete six-graph camera-operator family is now installed, compiled,
saved, and live-accepted on the integrated Client Director. Final Unreal
exports preserve the exact 18 / 259 / 105 / 147 / 116 / 6 node family and all
893 reciprocal links. Every final export passes its ownership and executable
contract: reset preserves inputs, policy, state, and the prior accepted result;
validation accepts 100 valid cases and rejects 30 failure cases; translation
and look each pass 160 forward/reverse cases; commit passes 100 complete
snapshots, 11 poisoned candidates, and three incomplete stages; and the tiny
coordinator retains the exact five-stage order.

Warm runtime passes 40 history-explicit frames forward and reverse plus five
validation failures and a direct poisoned commit. It proves authored body
components survive Unreal float round-tripping without being aliased to the
gimbal, carrier-frame input affects only local translation, external authorship
and downstream state remain untouched, and all defaults are restored. Three
automatic player-owned PIE sessions pass distinct Directed body/gimbal
authorship, carrier-frame isolation, and fail-closed accepted-state/result
preservation; PIE emits `GAME_WORLD_RESULT|PASS` and
`AUTOMATIC_RESULT|PASS` after restoring defaults.

Live acceptance exposed two verifier-only serialization assumptions, not graph
defects. Unreal adds `AutogeneratedDefaultValue="false"` beside an explicit true
bool, so the commit contract now parses only the explicit token. Unreal also
round-trips identity quaternions in named-component form, so reset/look
contracts accept exactly the compact generator spelling or the equivalent
native spelling. The runtime validator now compares authored quaternion
components at strict `1e-6` tolerance instead of impossible Python-double versus
Unreal-float bit equality and separately rejects body/gimbal aliasing.

The configurator rerun creates no variables or functions and verifies the exact
51-variable/six-function schema. Guarded shutdown closes both asset editors and
reaches `LogExit: Exiting.`. Only Client Director is reverse-synced; live and
mirror SHA-256 are
`8D5E47636D3B3CD87B5DF4FDE4AFAD003424A49C74DAA4DC60E47EFD15680332`.
A fresh NullRHI runtime repeats the full 40 + 40 + six matrix. A separate fresh
process cold-loads nine core assets, compiles all six Blueprints, and reports
zero errors. The complete MVP-required scaffold, including all six promoted
accepted-live exports, passes in 145.0 seconds. Next: commit/push this live
checkpoint, then continue the documented backend camera-mode/event-adapter
sequence toward debug dogfood. No UI work begins before dogfood.

The missing Carrier Freecam dependency is now frozen offline as
`carrier_frame_transport_reference.py` and
`carrier_frame_transport_blueprint_schema.json`. It consumes only the accepted
sampled path positions plus their exact total/fixed-step schedule. Authored body
and gimbal quaternions are deliberately absent; neither can be reused as the
carrier frame. The first basis uses world up unless parallel, then a
deterministic least-aligned axis. Later bases shortest-arc transport the prior up
vector and re-orthogonalize it, so the track is twist-minimizing and never uses
a Frenet normal. Holds find a deterministic nearest nonzero direction; a wholly
stationary path fails closed. Consecutive quaternions remain in one hemisphere.

Eight executable reference tests cover straight, planar, vertical, held,
reversing, seeded three-dimensional, partial-terminal, absolute-query-order,
malformed-input, and compiled-track tamper behavior. Five schema tests freeze 24
private variables, eight ordered functions, the exact upstream staging fields,
atomic publication, absolute-time evaluation, and non-authoritative ownership.
The complete scaffold owns both packages and passes in 145.3 seconds. Next:
build the deterministic reset, upstream-stage, validation, tangent, transport,
atomic-commit, compile coordinator, and evaluator graphs in that order while
Unreal remains closed.

`ResetCarrierFrameTransportV1` is now deterministic at 25 full / 24 paste
nodes with 24 / 23 reciprocal links. Its execution chain invalidates compiled
authority first, invalidates evaluation authority second, and clears stage
validity before touching four private candidate/compiled arrays. It then resets
only compiled timing, evaluation results, diagnostics, and scratch basis state.
The staged path positions, total/fixed-step schedule, and absolute elapsed-time
query are structurally absent and proven object-identical after execution.
Authored body/gimbal fields, `CameraTransform`, camera-operator state, playback
time, events, repositories, and server state are forbidden.

Both forms execute from exported reciprocal links against poisoned state, match
all exact defaults including native Vector/Quat spellings, and regenerate
byte-identically. The complete MVP-required scaffold owns the generator,
interpreter, and both checked-in snippets and passes in 142.5 seconds with
Unreal closed. Next: deterministically stage only the accepted desired-stream
positions and schedule, with explicit `source_invalid` failure and no body or
gimbal dependency.

`StageCarrierFrameTransportInputsV1` is now deterministic at 13 full / 12
paste nodes with 12 / 11 reciprocal links. It reads exactly desired-stream
compile validity, sampled positions, total seconds, and fixed step. Direct
execution invalidates stage authority and clears its diagnostic first. A valid
source snapshots all three values and publishes stage validity last; an invalid
source writes only `source_invalid` and preserves the prior staged positions and
schedule. Candidate, compiled, evaluation, operator, and external state are
structurally absent, as are authored body/gimbal and `CameraTransform`.

The exported-link interpreter executes 80 randomized valid snapshots and the
invalid-source preservation path in both full and paste forms. It proves the
position array is copied by value, protected object identities survive, and
each path visits exactly its intended execution nodes. Regeneration is
byte-identical, link integrity is exact, and the complete MVP-required scaffold
passes in 140.4 seconds with Unreal closed. Next: validate staged shape,
schedule, finite position values, and the existence of a usable path direction
without mutating the staged snapshot.

`ValidateCarrierFrameTransportInputsV1` is now deterministic at 74 full / 73
paste nodes with 97 / 96 reciprocal links. It requires a successful staged
snapshot, 2..65,536 positions, finite bounded total/fixed-step timing, and the
exact zero/integer-step/terminal schedule expressed by
`(count - 2) * step < total <= (count - 1) * step`. It checks every Vector
component for finiteness and separately proves that at least one position
differs from the first by more than the frozen squared epsilon. Holds,
reversals, and vertical paths remain valid; only a wholly stationary path is
directionless.

The graph writes only diagnostic/scratch state and never derives or publishes a
tangent. Its stable failures are `input_invalid`, `position_not_finite`, and
`path_has_no_direction`; validation authority publishes last on success. Both
forms execute 84 straight/held/reversing/partial/seeded valid paths and 14
stage/count/timing/schedule/finite/direction failure families without mutating
the staged snapshot or protected state. Exact regeneration and reciprocal links
pass, and the complete MVP-required scaffold is green in 142.6 seconds with
Unreal closed. Next: build the deterministic nearest-nonzero tangent track for
every sample, including holds, without reading authored rotation.

`BuildCarrierFrameTangentsV1` is now deterministic at 72 full / 71 paste nodes
with 112 / 111 reciprocal links. It clears only its owned tangent candidate,
requires successful validation, and evaluates the exact reference priority per
sample: centered difference first for interior samples, then immediate forward,
immediate backward, and nearest outward forward/backward candidates. The first
vector longer than `1e-9` is normalized and appended through one frozen append
site. Runs of held samples therefore inherit a deterministic nearby path
direction without introducing a Frenet normal.

Unexpected missing directions fail with `tangent_missing`; incomplete final
cardinality fails with `tangent_build_failed` and cannot publish scratch
validity. Both forms execute 104 straight/vertical/held/reversing/curved/seeded
paths forward and reverse, match the reference candidate priority component by
component, prove unit output, preserve source positions, and reject a forced
stationary path. Generation is byte-identical, reciprocal links are exact, and
the complete MVP-required scaffold passes in 141.1 seconds with Unreal closed.
Next: build the actual carrier quaternion samples by deterministic initial-basis
selection and shortest-arc parallel transport, keeping this tangent track and
authored body/gimbal immutable.

`BuildCarrierFrameTransportSamplesV1` is now deterministic at 128 full / 127
paste nodes with 205 / 204 reciprocal links. It initializes from world up, uses
the deterministic least-aligned X/Y fallback for vertical motion, and builds
each later frame by the shortest-arc quaternion from the prior tangent. The
prior up vector is rotated, projected back onto the new tangent plane, and
re-orthogonalized; a bounded cross-product fallback handles numerical collapse.
`MakeRotFromXZ` creates the basis through an already-proven native node, and an
explicit component dot/negation keeps consecutive quaternions in one
hemisphere.

The graph reads only the candidate tangent track and its own scratch/quaternion
candidate state. Authored body/gimbal, source positions, compiled/evaluation
state, operator state, playback, document, repository, events, and server state
are structurally absent. Both forms execute 104 straight/vertical/held/
reversing/planar/seeded paths forward and reverse against the frozen reference,
proving unit quaternions, exact forward/tangent alignment, stable planar world
up, deterministic vertical fallback, and hemisphere continuity. Regeneration
is byte-identical, reciprocal links are exact, and the complete MVP-required
scaffold passes in 142.7 seconds with Unreal closed. Next: preflight and
atomically copy the complete tangent/quaternion pair plus timing, publishing
compiled validity last.

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
- Do not use Blueprint Assist `Q` to repair frozen graph entry wiring. In the
  named-look acceptance it connected the visible seam but inserted 21 extra
  nodes; exact export rejected the 67-node result and immediate undo restored
  the expected 46 nodes / 62 links. Use the single explicit pin connection and
  verify exact post-compile topology.

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
post-boundary discontinuity diagnostics, named-look composition, the separate
viewer-local comfort layer, scalar-track engine, and synchronized thirteen-
channel lens/focus/effect frame assembly, and exact transactional engine
property application/restoration. Confidence is not yet claimed for
camera modes, events, keyboard
dogfood, UI, cooking, Workshop, G-Portal, deployment, or whole-mod completion.
