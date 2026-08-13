# Continuation Handoff

Last updated: 2026-08-13 after commit `6d0ce52`

This is the first file a fresh implementation session should read. It is a
high-signal continuation map, not a replacement for the authoritative evidence
in `implementation-plan.md`, `devkit-findings.md`, and
`blueprint-workflow.md`.

## Non-negotiable scope

- Continue backend implementation only.
- Do not start polished UI, cook, Workshop, G-Portal, or deployment work.
- Prove behavior end to end. Generated graph shape alone is not acceptance.
- Automate a finicky editor operation before repeating it manually.
- Commit and push every clean feature checkpoint.
- Never claim that the whole mod is complete.
- The next accepted product gate is full keyboard/debug dogfooding after the
  complete backend, not an early cook.

## Repository and clean starting state

- Repository: `T:\Projects\ExileDroneDirector`
- Branch: `main`
- Last implementation head: `6d0ce5271c956a7c8711ed627ca93bb1530a9ac6`;
  current HEAD should be the later documentation-only handoff commit and must
  equal `origin/main`
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
complete desired-airframe stream composition.

The last live-accepted trajectory commit is `8d8b603`:

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

## Current source-sampling bridge state

The missing seam is compiled-document/source sampling into the accepted desired
stream. It must sample position, distinct authored body orientation, distinct
authored gimbal orientation, and all ten smoothed flight-profile values on one
exact absolute-time schedule.

Four clean checkpoints are pushed after `8d8b603`:

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

These four checkpoints are offline-proven only. None of the new bridge graphs
has been installed, compiled, saved, cold-loaded, or executed by Enhanced.

## Next ordered implementation

Do not open Unreal yet. Finish the three remaining graph bodies and exported-link
interpreters offline first.

### 1. `BuildAirframeSourceGimbalSamplesV1`

- clear only the gimbal candidate
- preserve completed body/profile candidates byte-for-byte
- load distinct gimbal quaternions into the shared orientation compiler
- compile and sample the exact already-published schedule
- require evaluator agreement with position/body schedule metadata
- append one gimbal quaternion per successful sample
- failures set stage false and leave only a bounded private prefix

Sequential reuse of the one orientation cache is intentional. Body is fully
sampled before the cache is replaced by gimbal.

### 2. `CommitAirframeSourceSamplesToDesiredV1`

- invalidate `AirframeSourceCompileValidV1` first
- require stage true and exact 2..65,536 cardinality across all thirteen arrays
- require cardinality equals the published expected sample count
- copy all arrays, total, and step into accepted desired-stream inputs
- call `CompileAirframeDesiredStreamV1`
- publish source validity last only if desired and prebake validity are true
- direct preflight failure must not mutate downstream inputs; top-level reset
  owns complete transaction invalidation

### 3. `CompileAirframeSourceSamplingV1`

Keep orchestration tiny and policy-free. Exact order: reset, validate authored
shape, compile position/profiles/schedule, sample position/body/profiles, sample
gimbal, commit desired stream.

Add generators, snippets, interpreters, deterministic repeat checks, and files
to `tools/Test-Scaffold.ps1`. Update this handoff and both evidence documents.
Commit and push every clean slice.

## Live acceptance after the offline set

Once all seven bridge graphs are offline green:

1. create idempotent `Configure-AirframeSourceSamplingAssembly.py` modeled on
   `Configure-AirframeDesiredStreamAssembly.py`
2. add all 22 variables and seven functions
3. paste exact generated bodies through established automation
4. export and run contracts before compile
5. compile/save with an explicit save marker
6. export again and rerun contracts postcompile
7. run a CDO runtime harness against the independent oracle, warm twice and in
   an independent fresh NullRHI process
8. cover exact/partial schedules, all profiles, distinct body/gimbal, invalid
   authorship, component/evaluator/physical/downstream failure, poisoned repeat,
   immutability, and full union-state restoration
9. guarded shutdown; require `LogExit: Exiting.`
10. FromDevKit preview; expect only Client Director changed and review it
11. sync that package, prove live/mirror SHA-256 equality
12. fresh cold core-asset load and complete scaffold
13. commit and push the live-accepted bridge

## Critical design mismatch

The Python document model has distinct `body_rotation` and `gimbal_rotation`,
but the current Blueprint v1 document/waypoint bridge exposes one
`CameraTransform` rotation. Do not alias that rotation into both source arrays.
Resolve the document adapter explicitly after the sampling bridge is accepted.
This does not block current graphs because their schema already owns separate
body and gimbal quaternion inputs.

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
# Focused reference/schema
python tools\trajectory\test_airframe_source_sampling_reference.py
python tools\trajectory\test_airframe_source_sampling_blueprint_schema.py

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

Confidence is high in every checkpoint explicitly accepted above and in the
four new offline bridge checkpoints. Confidence is not claimed for the three
remaining bridge graphs, live bridge integration, document adaptation for
distinct body/gimbal authorship, lens/focus/effects, events, keyboard dogfood,
UI, cooking, Workshop, or whole-mod completion.
