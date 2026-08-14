# Continuation Handoff

Last updated: 2026-08-14 at the live camera scalar-track acceptance checkpoint

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
- Current implementation lineage starts from remote-equal `51cd7fa`, with the
  live camera scalar-track checkpoint described below; HEAD must equal
  `origin/main`
- Expected worktree: clean
- Git remote: `origin/main`
- Enhanced DevKit root: `F:\CEUE5Devkit`
- The Unreal editor was closed at this handoff.

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

## Offline camera channel-assembly state

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

## Next ordered implementation

Generate the nine channel-assembly graphs in frozen stage order, with exact
full/paste snippets, semantic interpreters, and scaffold ownership. Only after
the entire offline family is green, install and live-accept it in one editor,
including runtime, real-world PIE, guarded save/sync, cold load, and full
regression. Then implement
Directed / Free Look / Carrier Freecam backend modes, followed by event tracks
with bounded target adapters and authorization. Start each seam offline with an
explicit reference/schema and deterministic graph generators/interpreters,
then use one-editor compile/save/runtime/PIE/cold acceptance. After the complete
backend, expose temporary debug controls and logs, run attended dogfood, and
only then implement the polished UI.

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

Confidence is high in every checkpoint explicitly accepted above, including the
complete live source-sampling bridge and lossless compiled-document adapter with
post-boundary discontinuity diagnostics. Confidence is not claimed for
lens/focus/effects, camera modes, events, keyboard dogfood, UI, cooking,
Workshop, G-Portal, deployment, or whole-mod completion.
