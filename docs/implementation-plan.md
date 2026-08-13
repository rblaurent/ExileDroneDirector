# Exile Drone Director — Implementation Plan

Status: execution plan for Conan Exiles Enhanced DevKit development
Planning rule: every backend phase ends in structural contracts, programmatic
PIE acceptance, edge-case evidence, and a keyboard/debug dogfood surface.
Cooking is a later integration gate, not the next implementation milestone.
Release strategy: complete and prove the backend before investing in polished UI
Current internal build: `0.81.0-flight-profile-evaluator`

## 1. Delivery strategy

Development proceeds through backend capability slices rather than building all
UI, all math, or all networking in isolation. The first complete product loop is:

**Create private Flypath → capture two waypoints → save on server → publish →
second client plays → second client clones privately**

That loop establishes the camera boundary, client/server attachment, durable
identity, persistence, authorization, network transport, immutable publication,
local evaluation, and cloning. It is not considered ready for the UI or cook
gates until cinematic trajectory, rotation, timing, lens, event, restoration,
and failure semantics are also reachable through shortcuts and explicit debug
output. Subsequent UI work exposes this proven backend without redefining it.

## 1.1 Current implementation checkpoint

This section is the authoritative handoff. Detailed evidence remains in
`devkit-findings.md`; exact clipboard procedure remains in
`blueprint-workflow.md`.

### Atomic cinematic-pose composition checkpoint

- `ResetCinematicPoseV1`, `ValidateCinematicPoseInputsV1`,
  `CommitCompiledCinematicPoseV1`, `CompileCinematicPoseV1`, and
  `EvaluateCompiledCinematicPoseV1` are installed, compiled, saved, mirrored,
  and executable. Composition reuses the accepted position-route and quaternion
  orientation compilers on one duration array; it does not introduce another
  interpolation implementation.
- The five deterministic full/paste graphs contain 12/11, 27/26, 57/56, 6/5,
  and 65/64 nodes. Exact compiler-reconstructed live exports contain 12, 27,
  57, 6, and 65 nodes and pass the same reciprocal-link contracts. Combined
  compile validity publishes last only after exact component counts, starts,
  durations, and totals agree; combined evaluation validity publishes last only
  after both absolute-time evaluators agree on segment, local alpha, completion,
  and total.
- Warm and fresh NullRHI execution each accept 13 poses and 3,223 oracle
  evaluations, including the 512-waypoint ceiling, exact boundaries, every
  supported position curve/time profile, random and shuffled direct scrubs, and
  deterministic recompilation. Maximum position error is
  `3.410605131648481e-13`, maximum angular error is
  `1.032382731180714e-07` radians, and local-alpha error is zero.
- Eight authored compile failures, seven corrupt commit publications, eight
  corrupt evaluation publications, and all three non-finite elapsed values
  reach Blueprint and fail closed. Poisoned combined outputs clear, component
  publications remain unchanged by commit/evaluation checks, authored inputs do
  not mutate, and every touched class-default property restores.
- Every accepted scalar/vector/quaternion, adaptive-arc, position-route, and
  orientation runtime regression remains green. The full scaffold passes;
  guarded shutdown produced no crash reporter; a separate cold process loaded
  nine core assets and compiled all six Blueprints. Closed-editor live/mirror
  Client Director SHA-256 is
  `CF2A983EA78EBA040D65C3A2407DDA65CD326FD2C52C64D27B07A50BB33803BC`.
- Next is the ordered cinematic backend beyond pose composition: flight-profile
  behavior and camera/lens/focus/effect tracks, followed by shortcut/debug
  dogfooding. Polished UI, cook, Workshop, and whole-mod completion remain
  explicitly unclaimed.

### Flight-profile compile/evaluate checkpoint

- The first bounded flight-profile slice is installed, compiled, saved,
  mirrored, cold-loaded, and executable. It compiles one document default plus
  one optional override per segment into immutable profile IDs and ten numeric
  parameter channels. It does not yet claim profile-driven airframe/gimbal
  solving or procedural wind.
- Exact supported IDs are `cinematic_drone`, `hybrid`, `fpv_cinewhoop`,
  `fpv_freestyle`, and `fpv_long_range`. An empty override inherits the default;
  every nonempty override is still validated even if another segment is being
  evaluated. IDs are canonical, case-sensitive, and trimmed.
- Eight executable oracle tests pass distinct bounded presets, input
  independence, deterministic 511-segment compilation, shuffled direct lookup,
  invalid shapes/identifiers/types/indices, every corrupt parameter channel,
  and 200 seeded mixed tracks. Five Blueprint-schema tests freeze 53 explicit
  variables, seven ordered function boundaries, isolated resolver scratch,
  exact candidate/result channel separation, atomic publication, and fail-closed
  lookup.
- The seven exact post-compile live graphs contain 60, 37, 84, 58, 155, 5,
  and 182 nodes for reset, validation, resolver, candidates, commit, compiler,
  and evaluator respectively, with zero reroute knots. Reset clears all 22
  candidate/result arrays and 14 public validity/result scalars in one ordered
  chain.
  Validation uses 37 nodes to enforce segment count 1..511, exact override
  cardinality, one of five exact defaults, and empty-or-known identity for every
  override while keeping stage validity sticky-false after any rejection.
- Preset resolution and candidate construction are deterministic live graphs.
  The 84-node resolver clears its isolated 12-field result, follows one
  ordered exact-ID branch, writes all ten canonical parameters, and publishes
  resolver validity last. The 58-node candidate builder clears all candidate
  arrays, stages inherited/default IDs explicitly, calls the resolver per
  segment, rejects sticky-false on any failure, and appends the ID plus all ten
  channels in one ordered chain.
- Atomic commit and compilation orchestration are live. The 155-node
  commit invalidates prior publication first, proves all 11 candidate array
  cardinalities, re-resolves and compares every candidate parameter, publishes
  all 11 compiled arrays only after the completed sticky-valid scan, and writes
  compile validity last. The five-node compiler calls reset, validation,
  candidate construction, and commit in exact order.
- Indexed evaluation is live in a 182-node graph. It clears its own
  scratch and every public result, validates compile state/cardinality/index,
  scans and re-resolves every compiled segment with sticky evaluation validity,
  and publishes only the requested ID plus ten parameters with validity last.
- Warm and separate fresh NullRHI execution each pass 9 resolver cases, 7 valid
  compiles, 14 evaluations, the 511-segment ceiling, 12 invalid compile cases,
  24 candidate-corruption cases, 24 compiled-corruption cases, 5 bad indices,
  and complete state restoration. Non-finite values reach Blueprint and fail
  closed. A fresh cold-load compiles all six Blueprints with zero errors; the
  live and mirrored Client Director package SHA-256 is
  `B411E7414A74119D0F094D3CFD87C4C2772BCD17F40AB90DD80D12F20FBD55DB`.
- The next consumer seam is frozen offline: every segment owns its exact
  canonical profile at local alpha 0.5, while adjacent presets meet at one exact
  50/50 boundary value. Quintic smootherstep on each half makes all ten numeric
  channels C2 at both midpoint and waypoint boundaries, stays inside the convex
  hull of validated presets, and remains history-free under direct scrubbing.
  Its explicit Blueprint schema separates current/neighbor scratch from atomic
  result publication and restores the indexed helper to the requested segment.
- Next is generated reset/stage/publish/evaluate graphs for that smooth consumer,
  followed by deterministic cinematic, hybrid, and FPV airframe/gimbal
  behavior. Lens/focus/effect tracks and shortcut/debug dogfood follow. No
  polished UI, cook, Workshop publication, or whole-mod completion is claimed.

### Position-route absolute-time evaluator checkpoint

- `EvaluateCompiledPositionRouteV1` is compiled, saved, and warm-runtime
  accepted as the scrub-safe absolute-time composition boundary. It clears all
  public and primitive result validity first, validates compiled cardinality,
  scans every duration with sticky finite-positive validation while selecting
  the first containing segment, evaluates the timing profile, clamps its
  normalized distance alpha, stages the accepted arc slice, inverts arc length,
  and evaluates either exact linear interpolation or the accepted quintic
  vector primitive.
- Deterministic full/paste graphs contain 237/236 nodes with SHA-256
  `9616D10AC7D08CA2FCBE59366F0D9B70ADB705AD0E6605FA470D6F414A2F4607` /
  `13C72D6817F87C4673741C5ADD2B7DCD5ED45CD2864585A25972018C300EBAB4`.
  The exact post-compile 237-node export hashes to
  `766327739AEA1D71617364445C5E828BDE7B2B9A7BB4EB19FD12BA790E080D5F`.
- Warm compiled execution passes 17 routes and 3,605 evaluations, including
  shuffled direct scrubs, exact boundaries, all spatial/time-profile modes,
  and the 512-waypoint ceiling. Seventeen corrupt compiled-state families plus
  three non-finite elapsed values fail closed without mutating publication;
  complete state restoration passes. Maximum position error is
  `4.547473508864641e-13`.
- Runtime evidence caught and fixed three defects before acceptance: polynomial
  timing could exceed one by a few ulps near an endpoint; a malformed earlier
  duration could be skipped by selection; and late failures could leave helper
  validity true. The graph now clamps normalized distance, validates every
  duration sticky-false, and clears all three primitive validity flags on every
  post-selection failure.
- Fresh NullRHI execution repeats all 3,605 evaluations and rejection/restoration
  cases; fresh route-compiler and arc-inverter regressions also pass. Cold load
  loads all nine core assets and compiles all six Blueprints. Guarded shutdown
  kept crash directories at 25, closed-editor sync copied exactly Client
  Director, reverse sync found 17/17 unchanged, and live/mirror package SHA-256
  is `A995511B77A6D6E237561AAAEC03915B6773962E7162B234CA83F5218FB57208`.
  The complete `-RequireMvpAssets` scaffold passes. No UI, cook, Workshop, or
  whole-mod completion is claimed.

### Position-route selected arc-slice checkpoint

- `StagePositionRouteArcSliceV1` is compiled, saved, mirrored, and accepted as
  the bounded adapter between one selected compiled route segment and the
  existing cumulative arc-table inverter. It clears every primitive input and
  output first, validates compile state, selected-index/cardinality/slice
  bounds, finite nonnegative segment length, and finite distance alpha in
  `[0,1]`, then copies exactly the selected contiguous flat-table slice.
- Deterministic full/paste graphs contain 68/67 nodes with SHA-256
  `BB3AB3A286703BE4C59D466432374B6818D81A1B67D7FB9C9302E9950989563F` /
  `BB163444025E73E5D8852E038699B19B4E5C0CE223B2F0D51B2C211BF6EF656A`.
  The exact post-compile 68-node export hashes to
  `8FCC4E4564AA5640C27C74D9777FF2665173F59B11ACB4131A865A02287BA626`.
- Warm and fresh NullRHI execution each pass 726 valid selections spanning
  1,976 segments and 25,735 flattened samples, including unequal slice sizes,
  zero-length segments, out-of-order direct scrubbing, and the 512-waypoint
  ceiling. Fifteen malformed compile/index/cardinality/bounds/length/alpha
  families, including a maximum-integer start that would expose wrapped
  `start + count` arithmetic, all reach Blueprint and fail closed; poisoned
  destination state is cleared, source publication is unchanged, and every
  touched CDO property is restored.
- The complete warm position-route pipeline and downstream arc inverter remain
  green. Guarded shutdown kept crash directories at 25; closed-editor sync
  copied exactly Client Director, reverse sync found 17/17 unchanged, and the
  package hashes to
  `7906D5220E777F6D5EC6479F82143D0EB960608A3ECAFDB19985205E503BC87D`.
  Fresh compiler/inverter regressions, cold core-asset compilation, and the
  complete scaffold pass.
- The position-route assembly configurator is now safely idempotent: schema
  upgrades initialize only newly created variables and preserve every existing
  authored/CDO value. This removes the prior false failure on nonempty restored
  route inputs.
- Next ordered slice remains the full absolute-time
  `EvaluateCompiledPositionRouteV1` composition: segment selection, time-profile
  evaluation, this accepted slice adapter, arc inversion, linear/quintic
  spatial evaluation, completion semantics, and atomic public result commit.
  Cinematic dogfood controls, polished UI, cook, Workshop, and whole-mod
  completion remain unclaimed.

### Position-route compiler orchestration checkpoint

- `CompilePositionRouteV1` is compiled, saved, mirrored, and accepted as the
  single authored-input-to-compiled-route boundary. Its exact order is reset,
  validate inputs, compute waypoint velocities, build flattened segment arc
  tables, then atomically commit.
- The orchestrator is deliberately thin: six nodes in the full graph and five
  in paste form. Their SHA-256 hashes are
  `C30B61819CF6F9A7ACD41592B84F59B86205A6C91C773A7E999AE9EBED1AE5E8` /
  `2A11766A037E0CF8E4CDAFCCAD02ADDBDB04C5ABEAF6234C38B12D158D6995D4`.
  The exact post-compile six-node export hashes to
  `D4960A9F6236E706D4159D5E0422C41163B7DFBEA923C9128DD926AB6923D07A`.
- Warm and fresh NullRHI execution each stage only seven authored input fields
  and call the orchestrator once. Both pass 24 valid routes, 614 segments,
  5,701 arc samples, the 512-waypoint ceiling, 14 malformed-input families,
  replacement of a prior compiled route, exact candidate and compiled data,
  authored-input preservation, failure clearing, and full CDO restoration.
- Guarded shutdown kept crash directories at 25. Closed-editor mirror copied
  exactly Client Director, reverse sync found 17/17 unchanged, and the package
  hashes to `0FBE2FE9A52AA9A15681938B7B9FE22F30AF44DAADD4438A315893403AEB4758`.
  Fresh cold load and the complete scaffold pass.
- Next ordered slice is absolute-time evaluation through
  `EvaluateCompiledPositionRouteV1`. Cinematic dogfood controls, polished UI,
  cook, Workshop, and whole-mod completion remain unclaimed.

### Position-route atomic publication checkpoint

- `CommitCompiledPositionRouteV1` is compiled, saved, mirrored, and accepted.
  It clears all eleven compiled arrays, both compiled totals, the compile-valid
  flag, and every position-evaluation result before validating a candidate.
- Publication is atomic and candidate-only input remains immutable. A candidate
  is accepted only when waypoint/segment/flat-table cardinalities, cumulative
  starts, contiguous sample ranges, duration and distance totals, operation
  bounds, finite values, and exact `(u,distance) = (0,0)..(1,length)` segment
  endpoints all agree. Any rejection leaves empty invalid compiled state,
  resets the evaluation result segment to `-1`, and makes stage validity
  sticky-false.
- Deterministic full/paste graphs contain 182/181 nodes with SHA-256
  `FA86FC2A490C4F863BAABD5695885E0019B82327E393BF690DE7D45EFAF6DD1B` /
  `95B6961CFF70BF6AAA529AD877A7FF817E7F5B2DF81455B143A2B065F66C7FAD`.
  The exact accepted post-compile 182-node export hashes to
  `9A06CD6825699A31A9059666B3B25563EAF2ED45D03FD5547009EEBAA3A4004A`.
- Warm and fresh NullRHI compiled execution each pass 24 valid routes, 658
  segments, 7,679 flattened arc samples, the 512-waypoint ceiling, and 35
  corrupt/prior-invalid families. Both runs prove exact publication, candidate
  immutability, poisoned-state clearing, sticky rejection, evaluation reset,
  and complete CDO restoration. The upstream reset, validation, velocity, and
  segment runtime suites also remain green.
- Guarded editor exit added no crash directory (25 before and after).
  Closed-editor sync copied only Client Director and reverse preview found all
  17 managed files unchanged; the mirrored package hashes to
  `B389EFAB838464EC09FE2DF04204D9B24FCE418D3176A00D1CB13E034EFEE5C9`.
  Fresh cold load loaded nine core assets and compiled all six Blueprints, and
  the complete `-RequireMvpAssets` scaffold passed.
- Next ordered slice is the thin `CompilePositionRouteV1` orchestration
  boundary. This checkpoint does not claim route evaluation, cinematic
  dogfood controls, polished UI, cook, Workshop, or a complete mod.

### Cinematic scalar/vector/quaternion evaluator and control-compiler checkpoint

- `EvaluateTimeProfileV1` and `EvaluateQuinticScalarV1` are compiled and saved
  on `BPC_EDD_ClientDirector`. The first evaluates six bounded monotonic timing
  profiles; the second evaluates a clamped quintic Hermite scalar plus its
  first and second derivatives.
- Both functions fail closed on every non-finite staged scalar. Enhanced has no
  reflected scalar `IsFinite` Blueprint node, so version 1 uses the compiler-
  stable bound `-DBL_MAX <= x && x <= DBL_MAX`; the earlier `x - x == 0`
  predicate was rejected after compiled bytecode accepted NaN.
- Exact post-compile graphs contain 67 and 117 nodes with zero reroute nodes.
  Live and fresh-process compiled execution both pass 48 valid/5 invalid time
  cases and 69 valid/21 invalid quintic cases, restoring all staged properties
  afterward. Deterministic full and paste-form executable graph contracts are
  part of the complete scaffold.
- `EvaluateQuinticVectorV1` now composes that scalar kernel across X/Y/Z with
  one shared alpha. It atomically commits position, first derivative, and
  second derivative only after all three axes succeed; otherwise it clears all
  vector outputs and validity. Its exact post-compile graph is 78 nodes with
  zero reroutes and passes 103 valid plus 57 invalid executable graph fixtures.
- Live and fresh-process compiled execution independently pass 67 valid vector
  trajectories and all non-finite values that reach Blueprint. Enhanced's
  Python reflection sanitizes non-finite components of a native `Vector` before
  Blueprint execution (18 cases); that boundary is detected and reported by
  the harness rather than misclassified as evaluator acceptance.
- `EvaluateSphericalBezierQuaternionV1` is now compiled and saved. Four
  normalized finite quaternion controls and one clamped alpha are evaluated as
  a spherical cubic Bezier with six native shortest-arc SLERPs. Invalid inputs
  atomically clear validity and reset orientation to identity.
- Deterministic full/paste executable contracts and the exact 37-node
  post-compile live graph each pass 707 valid and 19 invalid fixtures. Warm and
  fresh NullRHI compiled execution repeat those counts with zero reflection
  sanitization and restore every staged class-default property.
- `ComputeOrientationLogDeltaV1`, `ComputeOrientationTangentRateV1`, and
  `BuildOrientationSegmentControlsV1` now compile the sign-aligned log-space
  delta, bounded time-domain angular tangent rate, and spherical Bezier control
  quaternions for one segment. The exact saved graphs contain 26, 85, and 76
  executable Blueprint nodes respectively.
- Deterministic source and paste graphs pass 554 valid plus 18 invalid fixtures;
  exact post-compile exports repeat the full suite. Warm and fresh compiled
  execution pass 142 valid plus 16 invalid cases, including zero/non-unit
  endpoint quaternions and invalid durations, while restoring every staged CDO
  property. Maximum observed errors are `1.604e-7` for log vectors,
  `9.357e-13` for tangent vectors, and `2.724e-7` radians for controls.
- This checkpoint completes the per-segment quaternion evaluator and its
  control primitives only. Multi-key assembly, segment/route evaluation,
  arc-length compilation, lens/focus/effect tracks, shortcut dogfood, polished
  UI, cook, and Workshop remain ordered work.
- `CompileOrientationTrackV1` now completes deterministic multi-key assembly,
  and `EvaluateCompiledOrientationTrackV1` consumes that published track by
  absolute time. It clamps negative scrubs to the first key, uses exact segment
  boundaries, returns the final key with completion at/after total time, and
  never depends on prior evaluation history. The exact saved evaluator graph is
  113 nodes with zero reroutes.
- Warm and fresh compiled execution each pass 3,016 frozen-oracle evaluations
  over 32 seeded tracks, plus 32 shuffled direct-scrub cases, nine malformed
  compiled-state cases, and all three scalar non-finite elapsed values. Maximum
  angular error is `3.2917740992269735e-7`; alpha error is exactly zero. This
  accepts orientation-track time evaluation only, not position/arc-length route
  compilation or the complete trajectory engine.
- `InvertArcLengthTableV1` now owns the validated serialized-table boundary for
  mapping normalized world distance back to curve parameter `u`. It requires
  equal arrays of at least two samples, exact `(u,distance)` endpoints
  `(0,0)..(1,length)`, strictly increasing `u`, nondecreasing cumulative
  distance, finite values, and nonnegative length. Alpha is clamped; a
  zero-length path remains stable; cumulative plateaus choose their left edge.
- The exact post-compile graph is 98 nodes with a reciprocal native-entry seam
  and zero reroutes. Warm and fresh compiled runtime each pass 4,266 valid
  table evaluations, including 195 segments from real adaptive linear and
  auto-cinematic compilations, plus all 16 malformed families and a shuffled
  direct-scrub case. Maximum error versus the frozen oracle is exactly `0.0`,
  stale outputs clear, and all eight staged CDO properties restore.
- This accepts inversion of an already-published cumulative table only.
  Adaptive table construction, position-route publication/evaluation, and the
  complete trajectory engine remain ordered work.
- Adaptive construction now has its frozen bounded iterative oracle and its
  first compiled transaction boundary. `ResetAdaptiveArcBuildV1` atomically
  clears all 10 work/candidate/published arrays and 12 scalar build/result
  fields. `ValidateAdaptiveArcBuildInputsV1` stages all six spatial controls
  through the accepted quintic-vector evaluator and accepts only finite curve
  data, positive finite tolerance, depth 1..12, and operation budget 1..8191.
- Exact post-compile graphs contain 33 and 36 nodes. Warm and fresh compiled
  runtime prove the 22-field reset, 64 valid seeded inputs, eight invalid
  scalar/budget families, stale-output clearing, and complete CDO restoration.
  Unreal reflection sanitizes NaN native Vector components before the
  Blueprint call; all 18 component placements are reported separately and are not
  misrepresented as executable Blueprint rejection evidence.
- `InitializeAdaptiveArcBuildV1` now clears all eight work/candidate arrays and
  resets operation count and candidate length before checking prior validity.
  A valid stage seeds exactly one interval `(0,start)..(1,end), depth 0` and the
  initial candidate sample `(0,start,0)`; an invalid stage leaves every array
  empty and never heals validity.
- Exact post-compile initialization is 31 nodes. Warm and fresh runtime each
  pass 64 randomized endpoint cases plus the invalid-prior-stage clearing case,
  with full CDO restoration. Reset, validation, and initialization are accepted;
  bounded processing, atomic publication, route integration, and the complete
  trajectory engine remain.
- `ProcessAdaptiveArcBuildV1` now consumes the synchronized interval stack with
  a bounded iterative loop, evaluates true quintic or selected linear
  midpoints, refines right-then-left for deterministic left-first traversal,
  and appends accepted samples and cumulative distance to candidate arrays.
  It fails closed on invalid prior state, malformed stack/candidate
  cardinalities, primitive failure, or an exhausted operation budget.
- Deterministic full/paste graphs contain 119/118 nodes; the exact saved
  post-compile graph contains 119 nodes. Warm and fresh compiled runtime each
  pass 23 deterministic linear/cinematic paths with 1,017 samples, exact
  operation counts up to 127, exact-budget success, one-short exhaustion, nine
  malformed/preflight cases, sticky failure, stale-state replacement, and full
  CDO restoration. All core assets cold-load and compile, the full scaffold
  passes, and the live/mirror Client Director SHA-256 is
  `581544AF09F830B2BD2945E0DF332088DF9DC63D10C0B24C1E4AEED2A1059A40`.
- Reset, validation, initialization, and bounded processing are accepted. Next
  was atomic candidate publication.
- `CommitAdaptiveArcBuildV1` now clears the prior public table before checking
  the candidate, requires successful bounded processing, five empty work
  stacks, exact candidate cardinalities, at least two samples, finite
  nonnegative length, exact `(u,distance)` endpoints `(0,0)..(1,length)`,
  strictly increasing `u`, and nondecreasing cumulative distance. Only a fully
  valid candidate replaces the public arrays/length and sets validity true.
- Deterministic full/paste graphs contain 95/94 nodes and the exact saved
  post-compile graph contains 95. Warm and fresh compiled runtime each publish
  32 oracle-built tables exactly and fail closed across 19 malformed/prior-state
  families, clearing poisoned public state and preserving sticky failure. Full
  CDO restoration, fresh core compilation, and byte-identical live/mirror
  package SHA-256
  `99BACEF4455F43FB0321F294BD13FC8C7743BA2D6693C6EBF8FBA7B32FC64055`
  pass.
- `BuildAdaptiveArcTableV1` now provides the thin, ordered transaction boundary:
  reset -> validate -> initialize -> process -> commit, with no bypass or
  intermediate publication. Deterministic source/paste graphs contain 6/5
  nodes and the exact post-compile graph contains 6.
- Warm and fresh NullRHI execution each pass 32 seeded oracle tables, six
  invalid or insufficient-budget requests, replacement of an earlier valid
  publication, exact operation counts, atomic clearing, and complete CDO
  restoration. Maximum observed distance/length errors are
  `1.08002496e-12` / `6.82121026e-13`; all nine core assets cold-load and all
  six Blueprint assets compile. Live/mirror Client Director SHA-256 is
  `433A3461D56686AB539033201F58E5E4D4F8FAAFC73DAF64E3CBEA9915E75565`.
- Adaptive per-segment table compilation is accepted end to end. Next is
  position-route composition/publication and its absolute-time/distance
  evaluator. The complete trajectory engine still remains; no UI, cook, or
  Workshop work is implied.
- Position-route composition has entered its first accepted transactional
  stage. `ResetPositionRouteCandidateV1` clears all 18 candidate, compiled, and
  evaluation arrays plus 14 scalar result fields while preserving all eight
  authored/evaluation inputs. It is idempotent and fail-closed, so no later
  validation or loop can expose stale data from an earlier route.
- Deterministic source/paste graphs contain 51/50 nodes with SHA-256
  `324E152D111E86C432CB80876307CE73DC6F2139B01CEC5B704AEDC1DEB00C1D` /
  `AC382699DE96DFFBE94CC1742585FE51EE33AB6EE1BF7660CCA641B90AB8B2AB`.
  The exact post-compile 51-node graph has SHA-256
  `D93A4110F2306910E75403A0B130D1BA00C5A283992C105C2468EDC64417D2B9`.
- Warm and fresh NullRHI execution independently prove all 32 output resets,
  eight preserved inputs, two consecutive idempotent calls, and full CDO
  restoration. A separate fresh process cold-loads all nine core assets and
  compiles all six Blueprints. Live/mirror Client Director SHA-256 is
  `FEC775EF7C15449B3170FBA9967326B4BA1823FF295D947FF0131FC1B6152B3E`.
- Only reset is accepted here. Position input validation, velocity/segment
  assembly, atomic publication, absolute-time/distance evaluation, lens and
  effect tracks, dogfood shortcuts, UI, cook, and Workshop remain ordered work.
- `ValidatePositionRouteInputsV1` now accepts only 2..512 finite waypoint
  positions with exactly one positive finite duration, supported spatial mode,
  and supported time profile per segment. Arc tolerance must be positive and
  finite; depth is 1..12 and operation budget 1..8191. Geometry accepts only
  `linear` or `auto_cinematic`; timing reuses the six already-proven profiles.
- Deterministic full/paste graphs contain 72/71 nodes with SHA-256
  `80DA4C892A9973BEF8DD945911994114CFEF081CCB96AFC444EF747F68659E73` /
  `B281119C47B854CEE39727F2F3A5FD79C52FFE43382B54CEC445D1600EB7BC4E`.
  The exact post-compile graph is 72 nodes with SHA-256
  `45969BA00C0E662A2958D73DBC4F0710E62528BE0BAE7679D724334C6146D0AD`.
- Warm and fresh compiled execution each pass five valid route sizes through
  the 512-waypoint ceiling and reject 28 malformed shape, setting, duration,
  curve, profile, and sticky-failure cases. All 12 injected NaN Vector
  components were sanitized by Enhanced reflection before Blueprint execution
  and are reported separately. Every touched CDO property restores. Next is
  waypoint-velocity construction; no UI, cook, or Workshop work is implied.
- `ComputePositionRouteVelocitiesV1` is now accepted as the next position-route
  transaction. It clears the candidate velocity array first, preserves the
  sticky validation verdict, emits one zero endpoint velocity per boundary,
  and emits one time-normalized monotone velocity per eligible interior key.
  Any adjacent `linear` segment forces that key to zero; `auto_cinematic`
  neighbors use the component-wise slope closest to zero when their signs
  agree and zero across a reversal or flat side.
- Deterministic full/paste graphs contain 83/82 nodes with SHA-256
  `03160E2376B1CA457EC08B8CAB2B24322DFA5D5D0B860883C7698751E009DB12` /
  `486FC1EC9421BFC8FA45009AFEE72C2DC8A8032E7859FB9D9154DFEF2F8AE6CB`.
  The exact post-compile 83-node graph has SHA-256
  `3759271529E7B769064D3EEB4BC45A2305119EA0875AB06F2DE9B617FD2E19B1`.
- Warm and fresh NullRHI execution independently prove 101 valid routes,
  10,968 axis values, the 512-waypoint ceiling, zero component error against
  the frozen oracle, prior-invalid stale-output clearing, and full CDO
  restoration. Fresh cold load again loads all nine core assets and compiles
  all six Blueprints. Live/mirror Client Director SHA-256 is
  `976374E79CF3E156AF20C283D612CD51B3EF801C8763742645534AB7168162B8`.
- Velocity construction alone is accepted here. Position segment assembly,
  candidate publication, absolute-time/distance evaluation, lens/effect
  tracks, dogfood shortcuts, UI, cook, and Workshop remain ordered work.
- `BuildPositionRouteSegmentsV1` is now accepted as the candidate-only position
  assembly stage. It clears every segment/flat-arc candidate channel first,
  refuses a prior-invalid stage or wrong velocity cardinality, converts each
  time-domain waypoint velocity into the segment's normalized-u domain, builds
  an exact per-segment arc table, and appends only complete segments. Early
  failure stays empty; late failure exposes only the deterministic completed
  prefix and never publishes compiled state.
- Deterministic full/paste graphs contain 78/77 nodes with SHA-256
  `BC9DB6FDF1229E1DFEAF5DEDC6404576DDD6B271CBBF813DF2187C1F270503EE` /
  `CE2801316AC6419580CB26C0BB801383B202AA1C77709FF2A8195B3F31790788`.
  The exact post-compile 78-node graph has SHA-256
  `6C437135BD353F0409D4D4ACDA43233352AFEC76613E7A9FC522769ABC305B9B`.
- Composition exposed two real Blueprint VM hazards in the accepted adaptive
  primitive. `ProcessAdaptiveArcBuildV1` now uses the native breakable loop so
  it stops when its synchronized stack is empty, and explicitly accepts a
  spatially linear interval after one pop. A linear segment therefore has the
  mathematically exact two-endpoint arc table instead of performing 127
  redundant quintic samples. Its deterministic full/paste graphs contain
  117/116 nodes with SHA-256
  `5E478579EA324EA4B35CEB7E579D3F9150135EB545E452E79AC0D90F15FD6F8D` /
  `C461CA26B8B765291EBE10B1EE6701218F3A17E263C2834467BCE1FBB8B7ED0E`;
  the exact compiled graph hash is
  `825B22142367BA64F19CD3EEAF23C1F6B556E364C92F2030C8C71753D9EAB222`.
- Warm and three independent fresh NullRHI runs prove 23 adaptive-process
  cases, 32 full adaptive compilations, and 32 position routes containing 662
  segments and 7,498 flat samples. The route suite includes 512 waypoints,
  exact `u`, maximum distance error `9.10e-13`, maximum length error
  `3.13e-13`, four fail-closed boundaries, and full CDO restoration. Every
  fresh log contains zero runaway/infinite-loop warnings. Cold load again
  loads nine assets and compiles six Blueprints; the complete scaffold passes.
- Live/mirror Client Director SHA-256 is
  `8AF62111F2235A8840CE02719A6920B96D45B51CC05D9912FE7FFC15634E4E25`.
  Atomic candidate publication is next. No compiled-route evaluation,
  dogfood controls, UI, cook, or Workshop readiness is claimed here.

### Cinematic orientation oracle checkpoint

- Version 1 now has an engine-independent multi-key quaternion compiler and
  evaluator. It normalizes and sign-aligns authored keys once, computes one
  time-domain angular tangent rate per waypoint, and evaluates time-aware
  spherical cubic Bezier segments by absolute time.
- The oracle proves exact keys, two-key shortest-arc constant-speed reduction,
  unequal-duration angular-velocity continuity, antipodal-key equivalence,
  unit outputs without sample sign flips, history-independent scrubbing,
  deterministic compilation, invalid-input rejection, and 100 seeded
  adversarial tracks.
- This remains the frozen target for multi-key track assembly. The per-segment
  spherical evaluator and its log/tangent/control primitives now implement the
  mathematical kernel; deterministic waypoint-to-segment assembly remains
  ordered work.
- The next Blueprint boundary is frozen in
  `tools/trajectory/orientation_blueprint_schema.json`: nine small ordered
  stages validate, align, compute deltas/rates/controls, atomically commit, and
  evaluate by absolute time. Candidate arrays are deliberately separate from
  compiled arrays so no failed loop can expose a partial track.
- The first two assembly stages are now compiled: a 34-node fail-closed reset
  clears every candidate, compiled, and evaluation channel, and a 29-node
  validator enforces `2..512` keys, exact `durations = keys - 1`, finite
  nonzero normalizable quaternions, and finite positive durations. Exact
  source/paste/post-compile contracts pass. Compiled runtime passes 4 valid
  boundary cases and 13 malformed/edge cases, including maximum cardinality
  and earlier-invalid/later-valid monotonic failure, with CDO restoration.
- This is a boundary checkpoint, not completed multi-key compilation. Alignment,
  deltas, rates, controls, atomic commit, and absolute-time evaluation remain
  the next ordered stages.
- `AlignOrientationWaypointsV1` is now the compiled third stage. It clears its
  candidate array, refuses to execute when prior validation is false, normalizes
  each authored key, and sign-aligns every later key against the prior accepted
  key using shortest-arc SLERP at alpha 1. Exact 15/14-node full/paste and
  post-compile contracts pass. Warm runtime matches 42 seeded oracle tracks,
  including antipodal and non-unit input, at `8.95e-8` radians maximum error;
  prior-invalid clearing and CDO restoration pass.
- `ComputeOrientationForwardDeltasV1` is now the compiled fourth stage. It
  clears stale candidate deltas, gates both entry and every loop iteration on
  sticky stage validity, stages each adjacent aligned quaternion pair into the
  proven `ComputeOrientationLogDeltaV1` primitive, and appends exactly one
  Vector delta per successful segment. Exact 20/19-node full/paste and
  post-compile contracts pass. Warm and fresh runtime match 64 seeded oracle
  tracks at `2.32e-7` maximum Vector error; prior-invalid, early primitive
  failure, later primitive failure, deterministic prefix, and CDO restoration
  cases pass.
- `ComputeOrientationTrackTangentRatesV1` is now the compiled fifth stage. It
  clears stale candidate rates, refuses a false prior stage, and constructs one
  time-domain angular tangent per aligned waypoint. Endpoints reuse their only
  adjacent delta/duration while interior keys use the previous and next pair;
  every calculation calls the already-proven tangent primitive. Stage failure
  remains sticky and exposes only a deterministic diagnostic prefix.
- Deterministic source/paste and exact post-compile contracts contain 60/59/60
  nodes. Warm and fresh compiled runtime each match 64 frozen-oracle tracks at
  `9.89e-13` maximum Vector error and pass prior-invalid, early primitive
  failure, later primitive failure, deterministic-prefix, stale-output, and
  full CDO-restoration cases. Guarded shutdown, exact one-package reverse sync,
  byte-identical live/mirror SHA-256
  `9630A366A78946A260DA4CDDB0D73C56DCDB6F8A638A5720FD29A67D6E06F583`,
  and fresh cold compilation of all core assets pass.
- `BuildOrientationTrackSegmentsV1` is now the compiled sixth stage. For every
  duration it stages aligned keys `i/i+1`, tangent rates `i/i+1`, and the
  segment duration into the proven spherical-control primitive. A successful
  item appends its cumulative start time and both controls, then advances the
  candidate total; primitive failure is sticky and leaves a deterministic
  successful prefix for diagnostics.
- Source/paste/exact post-compile graphs contain 37/36/37 nodes. Warm and fresh
  compiled runtime each match 64 multi-key oracle tracks, including cumulative
  segment starts and total duration, at `1.58e-7` radians maximum control error.
  Prior-invalid clearing and early/late primitive failure-prefix cases pass
  with full CDO restoration. Live/mirror package SHA-256 is
  `D93720E9BDD1F6777272A41E28B34ED09E5D1BC2360EF3B14E5C742837451F5A`;
  guarded exit, one-package sync, and fresh cold compilation all pass.
- `CommitCompiledOrientationTrackV1` is now the compiled atomic-publication
  stage. It resets all six compiled arrays, total/validity, and every evaluation
  output before validating the complete candidate. Publication requires exact
  candidate cardinalities, at least two aligned keys, finite positive durations
  and total, exact cumulative starts, and exact accumulated/candidate totals.
  Any failure clears the entire compiled/evaluation state and makes stage
  validity sticky-false; no partial track can become visible.
- Deterministic source/paste/post-compile contracts contain 85/84/85 nodes.
  Warm and fresh compiled runtime each publish 48 seeded candidates with exact
  component-for-component copies of waypoints and both control arrays (maximum
  publication error `0.0`), exact durations/rates/starts/total, and full result
  reset. Eleven malformed cases cover prior failure, every array-cardinality
  family, first/late cumulative-start corruption, wrong/non-finite total, and
  zero duration; all fail closed with CDO restoration. Live/mirror package
  SHA-256 is
  `BD82BF4AE047A4BBE2E365CDBDD6AB393E2AE65F6F5383D6DF3F0AA4D95A6BF8`;
  guarded exit, one-package sync, fresh runtime, and cold compilation pass.
- `CompileOrientationTrackV1` now runs the seven accepted stages in strict
  order: reset, input validation, key alignment, forward deltas, tangent rates,
  segment assembly, and atomic publication. Its deterministic source/paste/
  exact post-compile graphs contain 8/7/8 nodes with no branches or alternate
  publication path. Warm and two fresh-process runs compile 64 seeded tracks,
  replace a previously compiled track, reject eight malformed inputs, clear all
  stale compiled/evaluation state, and restore the CDO. Fresh oracle maxima are
  `2.48e-7` radians for quaternions and `1.04e-6` per tangent component. Cold
  compilation of every core asset and byte-identical reverse mirroring pass;
  Client Director SHA-256 is
  `D2962520E15F52A6993B3BB3274935EB75A6DBF3ED5915A38D1B026FBBC71CA7`.
- The next ordered slice is absolute-time segment evaluation. This checkpoint does not yet
  claim complete cinematic playback, UI, cook, or Workshop readiness.

### Live in the Enhanced DevKit

- Project source is `T:\Projects\ExileDroneDirector`; the installed Enhanced
  DevKit root is `F:\CEUE5Devkit` (Unreal Engine 5.6.1).
- `BP_EDD_ModController`, `BPC_EDD_ClientDirector`, and
  `BP_EDD_DroneCamera` provide the current runtime slice.
- F10 enters/exits local Drone Mode; F9 performs idempotent emergency exit.
- The camera is a non-replicated local view target. It never possesses or moves
  the player pawn.
- W/S, D/A, and E/Q fly; mouse controls pitch/yaw; wheel trims cruise speed;
  Ctrl is precision; Shift is boost; C/Z bank; H toggles horizon lock.
- `CaptureCurrentWaypoint`, `ReplaceSelectedWaypoint`, and
  `DeleteSelectedWaypoint` are compiled live functions with reciprocal native
  entry links. Every successful mutation now invokes `SyncDraftDocumentV1`,
  then `RefreshPathPreviewV1`, before feedback, so the complete typed document
  and visible path remain transactionally aligned with the six proven legacy
  channels.
- `StartLinearPlayback`, `UpdateLinearPlayback`, and `StopLinearPlayback` are
  compiled absolute-time functions. P toggles playback; active playback ticks
  suppress manual flight and waypoint edits. Completion holds the exact final
  authored transform until explicit stop, preventing horizon stabilization or
  manual input from pulling the camera off its last frame.
- The live 62-node/235-pin client EventGraph retains mutually exclusive K
  capture, R replace, and Delete removal shortcuts while inactive. Each
  successful mutation continues to shared dynamic feedback:
  `[EDD] Draft waypoints: N | selected: I`.
- Accepted capture, replace, and delete function bodies now emit stable
  log-only success/rejection diagnostics. They never print on screen, so
  authoring evidence remains available without contaminating cinematic output.
- Normal F10 exit, manual F9 emergency exit, and invalid-camera recovery each
  stop playback before restoring the player view.

### Runtime and structural evidence

- Two-player listen-server fixtures prove owning-client isolation, one local
  drone per client, unchanged controlled pawns, and exact view restoration.
- The selected-waypoint edit cycle proves two atomic captures, exact transform
  and lens replacement, survivor and empty deletion behavior, invalid-index
  no-ops, remote-client isolation, and restored drone class defaults.
- Physical PIE acceptance proves F10 entry, K capture, R replacement, Delete
  removal, and F9 restoration. The feedback build additionally proves a real K
  press emits `[EDD] Draft waypoints: 1 | selected: 0`.
- Pure reference tests prove direct-time linear evaluation, exact authored
  endpoints, equal segment duration, negative-time clamping, history
  independence, and shortest quaternion interpolation. A deterministic
  two-player PIE run through the real F10 entry route proves empty and
  single-waypoint no-ops, initial snap, absolute-time movement, exact final-frame
  hold, restart, explicit stop, client isolation, and unchanged possession/view
  restoration. It ended with `AUTOMATIC_RESULT:PASS`.
- Reviewed live graph snippets cover capture, replace, and delete. Their tests
  validate pin types, execution order, stable ID/hold behavior, all six array
  mutations, selection repair, and exact native function-entry linkage.
- The executable version-1 Flypath document oracle proves canonical lossless
  serialization under explicit `structural-v1` integrity, exact schema and
  waypoint/segment validation,
  optimistic revision conflicts, immutable published snapshots, owner-only
  editing, private-by-default creation/cloning, and clone attribution plus
  independence. Blueprint and server implementations must conform to it.
- `ST_EDD_Waypoint` contains the exact six-field lossless bridge and
  `BPC_EDD_ClientDirector` now compiles with a live `SyncDraftWaypointsV1`
  function. It checks all six channel lengths, positive unique IDs, finite
  camera scalars, positive focal length/aperture, and non-negative focus/hold
  values before mutation. It preserves the prior typed snapshot on any
  rejection, clears only after every guard succeeds, and rebuilds
  `DraftWaypointsV1` in ID-array order.
- The pure `SyncDraftWaypointsV1` oracle proves all-or-nothing lockstep
  validation, positive unique IDs, finite/valid camera scalars, ordered exact
  value copies, empty drafts, and snapshot independence. The live Blueprint now
  matches that complete preflight contract. `DraftWaypointsV1` is the validated
  authoritative read-side snapshot; the legacy arrays remain transitional
  write-side mutation channels until the authoring functions are migrated.
- `ST_EDD_Segment` and `ST_EDD_FlypathDocument` now contain the exact checked-in
  version-1 Blueprint schema. The client component compiles with empty
  `DraftSegmentsV1` and default-constructed `DraftDocumentV1` members. The
  schema/configurator contract is deterministic, executable, and idempotent;
  document population is deliberately the next transactional slice.
- `SyncDraftDocumentV1` is now a compiled, saved 124-node/552-pin live function.
  It invokes the typed waypoint preflight, reconciles surviving adjacencies by
  exact endpoint IDs, preserves every authored field of the first valid unused
  prior segment, allocates new monotonic segment IDs, rejects integer
  exhaustion, recomputes total duration, preserves editable document metadata,
  clears the stale content hash, and publishes `DraftSegmentsV1` plus
  `DraftDocumentV1` only after every guard succeeds. Nine pure executable cases
  cover the same transaction contract. A three-phase production-path PIE run
  now proves empty/single/two-waypoint rebuilds, exact endpoint references,
  segment ID `1`, repeat-sync idempotence, preservation of an authored `7.25`
  second Catmull-Rom/ease-in-out segment and document metadata, stale-hash
  clearing, malformed-channel rollback, and exact test-default restoration. It
  ended in `EDD_DOCUMENT_SYNC_PIE:AUTOMATIC_RESULT:PASS`.
- The exact native UE 5.6 Make/Break serialization for `ST_EDD_Segment` and
  `ST_EDD_FlypathDocument` is checked in and contract-tested. The generated pin
  suffixes, nested array element types, defaults, directions, and the native
  omission of explicit empty-string defaults are now stable inputs to the
  deterministic graph builder rather than undocumented editor knowledge.
- The generated 84-node/362-pin waypoint sync graph and copied post-compile
  Unreal round-trip both pass reciprocal-link and semantic contracts. A production-path
  PIE run
  proved empty rebuild, two exact captured struct values, repeat-sync
  idempotence, and clean camera restoration, ending in
  `EDD_WAYPOINT_STRUCT_PIE:AUTOMATIC_RESULT:PASS`.
- The generated capture/replace/delete bodies and their copied live Unreal
  round-trips now require the sync call on every successful execution path.
  An adaptive production-path PIE edit cycle proved exact typed parity after
  capture 1, capture 2, replacement, survivor deletion, empty deletion, and
  invalid-edit no-ops. It ended in
  `EDD_WAYPOINT_PIE:AUTOMATIC_RESULT:PASS`; the optional second-world isolation
  branch was explicitly skipped in that one-player run and remains covered by
  the earlier two-player authoring acceptance.
- Repository scaffold, semantic graph contracts, Python syntax, and the 1 GiB
  repository budget pass. Tracked source is only a few MiB; DevKit and cooked
  outputs are never committed.
- `BP_EDD_PathPreview` now has a typed `PreviewDocumentV1` seam, explicit marker
  and line-scale defaults, and two non-colliding movable HISM pools using Engine
  sphere and cube meshes. `ClearPreviewV1` is a compiled and saved five-node
  live function that clears `WaypointMarkersV1` before `SegmentLinesV1`; its
  fresh Unreal export has 11 pins and passes reciprocal-link plus dedicated
  semantic contracts. `RebuildPreviewV1` first established a compiled
  14-node/60-pin marker slice: clear both pools, guard on `PreviewEnabled`, break the typed
  document, iterate ordered typed waypoints, preserve each camera location and
  rotation, replace scale with uniform `MarkerScaleV1`, and add one world-space
  sphere instance. The live function is now the compiled 34-node/143-pin combined
  marker-and-segment slice. After each marker it bounds-checks `index + 1`, reads
  the adjacent typed waypoint, rejects distances at or below `0.001`, and adds
  one world-space cube to `SegmentLinesV1`. The cube is centred with transform
  interpolation at `0.5`, oriented by `FindLookAtRotation`, scaled on local X by
  `distance / SourceCubeExtentV1`, and scaled on Y/Z by `LineThicknessV1`.
  The generated full/paste graphs and checked post-compile Unreal export pass
  reciprocal-link and dedicated semantic contracts. A four-phase
  production-path PIE gate proved 1 marker/0 segments, 2 markers/1 exact segment,
  2 coincident markers/0 segments, exact marker and segment transforms,
  clear-to-zero behavior, class-default restoration, and temporary-actor cleanup.
  A seven-case pure geometry oracle also locks ordered marker placement,
  midpoint/orientation/length scaling for linear segments, vertical paths,
  degenerate adjacency suppression, invalid-value rejection, and history
  independence. Visible marker and linear-segment runtime output are now claimed.
- `BPC_EDD_ClientDirector` now owns exactly one nullable
  `PathPreviewActorV1`. `RefreshPathPreviewV1` reuses a valid actor or spawns one
  collision-independently with an explicitly wired identity transform, copies
  `DraftDocumentV1`, and rebuilds it. `DestroyPathPreviewV1` clears both pools,
  destroys the actor, and resets valid or stale references to `None`. Both
  functions compile, save, round-trip through Unreal, and pass reciprocal-link
  plus semantic contracts.
- Enter refreshes on both successful camera paths; capture, replace, and both
  delete success paths sync the full document then refresh; normal exit destroys
  the preview before view restoration. A two-client PIE gate proved one actor on
  entry, reuse across repeated refresh/entry, 2 markers and 1 segment through the
  real capture path, playback coexistence, idempotent exit/destroy, fresh re-entry,
  final cleanup, and remote-world isolation. It ended in
  `EDD_PATH_PREVIEW_LIFECYCLE_PIE:AUTOMATIC_RESULT:PASS`.
- Bounded draft history now exists in the live client component. Six compiled
  functions implement capped undo/redo stacks, exact document/selection/next-ID
  snapshots, redo-branch invalidation, and transactional restore through the
  typed document plus all six transitional authoring arrays. The cap is 64 and
  empty-stack operations are no-ops.
- Capture, replace, and delete now call `RecordUndoSnapshotV1` exactly once after
  their last validity guard and before their first array mutation. Invalid
  camera/index attempts remain terminal and consume no history. Deterministic
  full/paste generation, fresh live Unreal exports, compiler results, reciprocal
  links, and semantic contracts all pass for the three mutation paths.
- Ctrl+Z/Ctrl+Y now enter the compiled undo/redo core only for the owning local
  controller while Drone Mode is active, the camera is valid, and playback is
  inactive. Either Control key is accepted; an undo chord cannot also execute
  the Z roll binding. Applied and empty-stack paths have stable diagnostics and
  terminate the tick. The 86-node/355-pin EventGraph compiled live, saved,
  round-tripped from Unreal, and passes authoring, feedback, playback, history,
  deterministic-generation, and idempotence contracts in the full scaffold.
- The isolated draft-history PIE gate is now a single deterministic command:
  `tools\Run-DraftHistoryPIE.ps1`. It launches one mod-aware editor, loads
  AlmostEmpty, starts PIE through `LevelEditorSubsystem`, applies the survival
  guard, and executes the public Enter/Capture/Undo/Redo/Exit operations. One
  run captured 65 waypoints, proved the live 64-transaction cap, restored exact
  typed documents/source arrays/preview instances through undo and redo, proved
  branch-edit redo invalidation, verified no-camera capture, empty redo, invalid
  replace, and invalid delete through full before/after fingerprints, restored
  the exact original view, ended PIE, emitted a run-scoped PASS, and closed the
  editor. Deterministic graph contracts prove the F10/K/Ctrl+Z/Y/F9 wiring;
  final physical routing belongs to the attended cooked-client gate.
- Clean Frame is now a compiled client-local presentation primitive. F7 is
  polled after owner, Drone Mode, and camera-validity guards but before playback
  arbitration, so it remains available during free flight, authoring, and
  playback. Enter captures Conan's independent `Popup` and `HUD` category
  states, disables both categories, hides the remaining BaseGameHUD
  notification layer when present, hides the path-preview actor without
  rebuilding it, and commits `CleanFrameActiveV1`. Exit restores the captured
  category states exactly, restores notification visibility consistently with
  the captured HUD state, reveals the intact preview, and clears the active
  flag. Repeated enter/exit calls are idempotent.
- Normal `ExitDroneMode` now invokes `ExitCleanFrameV1` before preview teardown
  and view restoration. `EmergencyExitDroneMode` already delegates to that
  normal exit primitive, so F9 and invalid-camera recovery share the same HUD
  restoration boundary. The live 89-node EventGraph and all three Clean Frame
  functions compile green and pass reciprocal-link plus semantic contracts.
- Focused PIE acceptance deliberately started with divergent Conan category
  states and proved exact HUD/Popup capture and restore, preview hide/show,
  repeated-toggle stability, normal-exit restoration, emergency restoration,
  and preview destruction. It ended in
  `EDD_CLEAN_FRAME_PIE:AUTOMATIC_RESULT:PASS`. The synthetic fixture does not
  instantiate Conan's normal `BaseGameHUD`, so final visual proof of the
  remaining notification widgets and every native HUD element belongs to the
  first cooked-client acceptance.

### Reproducible graph evidence

- `Build-ClientWaypointEditDispatch.py` produces the proven 43-node K/R/Delete
  dispatch; `Build-WaypointFeedbackDispatch.py` extends it to the live 51-node
  feedback graph; `Build-LinearPlaybackDispatch.py` extends that to the live
  62-node playback-arbitrated graph.
- The generated graph and the copied post-compile Unreal round-trip both pass
  generic reciprocal-link validation, capture/edit semantics, and the dedicated
  feedback contract. The contract caught and prevented an invalid first draft
  whose string defaults were discarded during Unreal reconstruction.

### Not implemented yet

- No polished editor UI, timeline, cinematic
  curves, lens playback, routed client/server save/load,
  sharing, permissions, cloning, or event execution exists yet. The client-owned
  preview actor renders validated markers and linear segments, while current
  playback remains deliberately limited to equal-duration transform interpolation
  over the transient draft.
- Draft waypoint data is client-local and transient. Other server members
  cannot see or play it.
- A server-owned alternating-slot `SaveGame` storage asset now has idempotent
  generation tooling and passed exact Unicode/array round trips across two fresh
  Enhanced DevKit processes. Repository command graphs and client/server routing
  are not implemented yet, so this proves the adapter boundary, not end-user save.
- The server-only `BP_EDD_FlypathRepository` actor now compiles with versioned
  active state, request/result staging, bounded policy, typed draft-document
  exchange, JSON scratch objects, and separate codec/validation/storage/CRUD
  function seams. Its evolved state now also includes derived metadata-index,
  copy-on-write candidate, and typed SaveGame scratch channels. The bundled
  PlayFab JSON object passed a nested Unicode round trip and its insertion-order
  behavior is fixed by acceptance tests.
- Deterministic, complete and body-only graph sources exist for
  `ResetRepositoryResultV1` and `FindRecordIndexV1`, and both bodies are now
  installed in the live repository actor. The actor compiled successfully,
  reported `All Saved`, survived a fresh-process cold load, and was synchronized
  back to Git with an exact SHA-256 match. Native round-trip exports prove the
  function entries and reciprocal links, reset defaults/metadata clearing, and
  derived-ID lookup. This is executable repository-core plumbing, not yet full
  private CRUD.
- `LoadDraftV1` is now the first accepted private-CRUD boundary. It resolves the
  derived record index, returns `NotFound` without leakage, requires exact owner
  account identity before decoding, rejects corrupt/noncanonical envelopes, and
  returns the canonical envelope, current revision, and typed draft only to the
  owner. `ResetRepositoryResultV1` now also clears `ResultDraftDocumentV1`, so a
  denial after a successful load cannot expose stale typed data. Generated
  full/paste graphs, exact post-compile exports, clean compile/save, a real
  compiled-actor five-case runtime probe, and fresh-process cold load all pass.
- `CreatePrivateFlypathV1` is now the accepted private write boundary. The
  server-staged ID is deterministic and collision-checked; new records are
  owner-bound, private by default, revision 1, strictly validated and encoded,
  and appended through the accepted copy-on-write persistence writer. Derived
  indexes change only after a real committed SaveGame rewrite. Generated
  full/paste graphs are deterministic, the exact compiled graph round-trip
  passes its semantic contract, marked compile/save is clean, and the compiled
  actor proves invalid scalar requests, title/region/owner/serialized limits,
  collision isolation, deterministic A/B generations, owner-only readback, two
  persisted records across a fresh restart, wrong-owner denial, fixture cleanup,
  and cold loading. This checkpoint does not claim the remaining CRUD or mod.
- `ListMineV1` is now the accepted owner-filtered metadata listing boundary.
  It clamps offset/limit, filters exclusively through the derived owner index,
  sorts by `updatedUtc` descending with `flypathId` descending as the stable
  tie-break, emits metadata-only JSON, and never writes authority or SaveGame.
  Generated full/paste graphs, exact post-compile exports, marked compile/save,
  compiled-actor success/failure/edge cases, guarded restart recovery, fixture
  cleanup, and a separate cold load all pass. This accepts private listing only;
  delete, publication/discovery, clone, playback, trajectory, events, and UX
  remain ordered work.
- `DeleteFlypathV1` is now the accepted owner-only optimistic private-delete
  boundary. It authorizes through the derived owner index before decoding,
  validates decoded/index identity and the expected draft revision, removes the
  record only from the copy-on-write candidate, appends one tombstone, and
  mutates all derived arrays only after the accepted two-phase SaveGame writer
  commits. Generated full/paste graphs, an exact post-compile export, marked
  compile/save, executable rejection and success cases, a guarded restart,
  second alternating-slot delete, final reload, fixture cleanup, and an
  independent cold compile all pass. This accepts private CRUD only; publishing,
  discovery, cloning, playback, trajectory, events, keyboard dogfood, and UX
  remain ordered work.
- Runtime persistence integrity is frozen as explicit `structural-v1` after an
  Enhanced reflection probe found no Blueprint/Python digest helper. Canonical
  envelopes now declare the mode, require reserved hash fields to remain empty,
  reject unknown/missing fields and all semantic inconsistencies, and recover
  past a corrupt newest committed generation. The 57-test document/repository
  suite, complete scaffold, and fresh-process cold asset load pass. This does
  not claim cryptographic tamper detection; private save/list/delete remain.
- The physical two-slot SaveGame layout now has a dedicated 11-case executable
  oracle instead of relying on the logical per-record storage model. It locks
  deterministic inactive-slot selection, stage/commit ordering, generation
  increments, uncommitted-candidate rejection, record-granular corrupt-newest
  fallback, newer tombstone masking, monotonic/disjoint tombstones, fail-closed
  malformed tombstone channels, deterministic ordering, persistence failure
  isolation, invalid-header rejection, and equal-generation split-brain
  rejection. Blueprint persistence graphs must match this contract exactly.
- The complete Enhanced PlayFab JSON Blueprint fixture is now harvested,
  compiled, natively round-tripped, and semantically tested: 22 calls/87 pins
  cover canonical construction, string/bool/float/object fields and arrays,
  explicit nulls, generic values, `HasField`, `IsNull`, `EncodeJson`, and
  `DecodeJson`. The disposable probe asset was deleted in a fresh process.
  Repository codec graph composition can now proceed deterministically without
  further action-menu discovery.
- The repository service schema now owns dedicated document/record codec
  staging, including explicit draft/published documents, owner/metadata fields,
  optional-payload flags, source attribution, `ScratchSourceJsonV1`, and
  `ScratchSourceDocumentJsonV1`. The complete schema is applied to the live
  `.uasset`; its existing core/encoder functions and new decoder functions were
  re-exported and contract-tested after the shared asset resave. Quaternion
  conversion reflection proves the Transform bridge can emit/consume the
  canonical normalized quaternion representation without changing the
  persisted schema.
- Quaternion codec forms are harvested, but Enhanced 5.6.1 cannot safely paste
  the split return pin of `Conv_RotatorToQuaternion`: it asserts in
  `K2Node.cpp:1360`. The accepted encoder uses the unsplit conversion followed
  by the separately harvested native `BreakQuat` call. Both fixtures and the
  production graph are contract-tested; the toxic split form is explicitly
  rejected before any live paste.
- `EncodeWaypointV1` is now installed and accepted in the live repository
  actor. The real editor reconstruction survived without a new crash, compiled
  green, exported as 25 nodes/112 pins, passed complete semantic contracts,
  saved through Unreal's API, survived a fresh-process cold compile, and was
  mirrored back to Git with an exact SHA-256 match. Integer waypoint IDs use an
  explicit `Conv_IntToDouble` bridge before PlayFab JSON numbers.
- `EncodeSegmentV1` is now installed and accepted beside it. The post-save live
  export is 14 nodes/57 pins, covers all six segment fields, and uses explicit
  integer-to-double bridges for `segmentId`, `fromWaypointId`, and
  `toWaypointId`. It compiled with zero Blueprint/K2 errors, saved through
  Unreal's API, survived fresh-process cold compilation, and was mirrored with
  an exact live/Git SHA-256 match.
- `EncodeDocumentV1` is now installed and accepted as the deterministic root
  document encoder. Its post-save live export is exactly 37 nodes/146 pins,
  contains zero incidental reroute nodes, encodes all scalar metadata plus
  ordered segment and waypoint object arrays, and passed the semantic contract
  before and after compile/save. It survived fresh-process cold compilation and
  is mirrored with exact live/Git SHA-256
  `52DF21CC7428D0472549E0233F3633FF9C0973887B347F005413C1EBA437DCF9`.
- Decoder prerequisites are accepted from a real Enhanced editor
  round-trip. Exact string equality and split-input `Quat_Rotator` compiled
  green; the generic array-item form canonicalized to wildcard while unlinked
  and will specialize to PlayFab float only in the connected decoder graph.
  The shared clipboard cloner now rewrites split-pin `SubPins`/`ParentPin`
  GUIDs, and the contract rejects every stale internal reference. Separate
  source JSON scratch strings prevent nested re-encoding from overwriting the
  document text being validated. Both variables and all decoder bodies are now
  installed and accepted live.
- All three decoder bodies are now generated and semantically closed offline.
  Full and body-only graphs pass structural validation and exact contracts:
  `DecodeWaypointV1` is 38 nodes/136 pins (37/135 paste),
  `DecodeSegmentV1` is 21/67 (20/66 paste), and `DecodeDocumentV1` is 46/167
  (45/166 paste). Root JSON failure and numeric-array arity failure terminate
  before field or item reads; valid paths stage typed structs, call accepted
  encoders, and commit only canonical equality. The full scaffold owns these
  tests.
- All three decoders are now installed in the live Enhanced repository asset.
  Exact target identity was proven before each paste; live graph contracts
  passed before and after compile/save with the same 38/136, 21/67, and 46/167
  shapes. The repository core and all three encoders were also re-exported and
  passed after the schema resave. A fresh commandlet loaded and compiled all
  nine core assets with `EDD_COLD_LOAD|RESULT|PASS`. The live and Git-mirror
  repository SHA-256 is
  `C0E8C7F3368E873C1774E8CBDADC8F402EF96320AFBCA9A7D6BCA279ED56E59F`.
- The complete record-envelope encoder is now accepted live. The published
  fields helper is 17 nodes/57 pins, source attribution is 17/57, and the root
  record encoder is 44/157. Post-compile copy-backs pass exact contracts for
  canonical ordering, explicit null states, typed revision bridges, document
  isolation, and native-entry reachability. All eight pre-existing repository
  graphs also passed fresh live regression exports after the shared save.
  A new cold process loaded and compiled all nine core assets with zero errors;
  live and mirror repository SHA-256 is
  `DB56429B5F83CBC6923D0761FA6B62A01A858C526A8B6AE3C963ED13AE655A64`.
- The matching strict record-envelope decoder is now accepted live. Published
  fields are 16 nodes/53 pins, source attribution is 19/67, and the root is
  50/180. The root resets validity, preserves the complete input, branches on
  `DecodeJson`, rejects a non-object `record` before field reads, stages every
  typed field through the accepted document decoders, and commits validity only
  when `EncodeRecordV1` regenerates the exact canonical source. Full live
  copy-backs pass before and after compile/save, and all eleven pre-existing
  repository graphs pass fresh regression exports after the shared asset save.
  The wide root body uses a compact folded paste-only layout so Unreal keeps its
  first executable near the native entry without changing node identities or
  links. A fresh commandlet compiled all nine core assets with zero errors; the
  live and Git-mirror repository SHA-256 is
  `DBCCCACC223F164276AAE887C804CCEB2F9F30F399019302BF72B7DAFCD22B2B`.
- The complete structural/semantic validation layer is now accepted live.
  `ValidateWaypointV1` is 66 nodes, `ValidateSegmentV1` 40,
  `ValidateDocumentV1` 47, `ValidateRecordPublishedV1` 18,
  `ValidateRecordSourceAttributionV1` 12, and `ValidateRecordV1` 47. The
  230-node live round-trip suite proves finite and domain-valid camera values,
  unit scale, positive unique IDs, exact adjacency, finite positive segment
  durations, required/versioned document metadata, exact accumulated duration,
  private/public policy, optional published-snapshot rules, revision ordering,
  and clone-attribution requirements. Generated full graphs, compact paste
  graphs, exact live exports, repository-wide compile/save, and a fresh
  `-ModDevKit -NullRHI` cold compile all pass. Live and Git-mirror repository
  SHA-256 is
  `AF95AA2E9DF5F3AFEC28307A0B441CE398E0D7FC5B3727385930A1F184C96E5B`.
  Canonical whitespace trimming and canonical/non-reversed UTC timestamps are
  still enforced by the executable repository oracle but not yet by these
  Blueprint validator graphs; persistence/CRUD must not claim full oracle
  parity until those checks are implemented or placed at a proven boundary.
- The modular alternating-slot state layer is now accepted in the live
  repository actor. `ResetRepositoryStateV1` is 25 nodes,
  `ValidateStorageHeadersV1` 31, `PreparePersistenceCandidateV1` 14, and
  `CommitPersistenceCandidateV1` 10. Sixteen explicit A/B scratch members hold
  existence, schema, generation, commit, reserved hash, record envelopes,
  tombstones, and derived header validity. Generated full/paste graphs, exact
  live exports before and after compile/save, the complete semantic suite, and
  a fresh `-ModDevKit -NullRHI` cold compile all pass. The synchronized live and
  Git-mirror repository SHA-256 is
  `DCE427182D85FAECEEBB78B209A9DD5CF120689635D2F9ECDEA959E801596F88`.
  These functions deliberately own state transitions only: native SaveGame
  load/write calls and record-granular recovery remain the next slice.
- The exact Enhanced 5.6 native SaveGame seam is now harvested from a green
  compile and enforced by structural contracts. `DoesSaveGameExist`,
  `LoadGameFromSlot`, `CreateSaveGameObject`, and `SaveGameToSlot` are impure
  `GameplayStatics` calls in this build. Selecting `SG_EDD_RepositoryStorage`
  specializes Create's return pin, while Load still returns base `SaveGame` and
  requires an executed typed cast. Typed storage property get/set forms are
  captured too. This proves node construction, not connected repository I/O.
- Raw alternating-slot reads are now accepted live. The 19-node
  `ReadRepositoryStorageSlotAV1` and `ReadRepositoryStorageSlotBV1` functions
  each own existence, load, executed typed cast, and staging of all six storage
  fields. The 5-node `ReadRepositoryStorageSlotsV1` coordinator owns only
  reset -> A -> B -> header validation. All three exact exports pass semantic
  contracts before and after compile/save and survive a fresh headless cold
  compile. Missing slots and cast failures terminate locally; an existing slot
  whose load fails remains reset and is rejected by header validation. These
  functions do not choose authority, decode/recover records, replace active
  memory, or set `RepositoryLoadedV1`.
- Deterministic recovery ordering is now accepted live. Eight narrow functions
  reset recovery scratch state, compare ordered string arrays exactly, compare
  equal-generation peers, stage A-only/B-only/A-newer/B-newer candidates, and
  select the newest eligible committed slot. Identical equal-generation peers
  use deterministic B-only tie-breaking; divergent equal-generation peers fail
  closed with `DivergentEqualGeneration`. Generated full/paste graphs and exact
  live exports pass structural and semantic contracts before and after
  compile/save. A fresh nine-asset cold load emitted
  `EDD_COLD_LOAD|RESULT|PASS` with zero errors. Live and mirror SHA-256 is
  `92158F96ED04E3ABA8C23659945CF8A53310F7E771A1823C2D3D6F021A0314B4`.
  This checkpoint orders raw slot candidates only: it does not validate or
  merge tombstones, recover individual record envelopes, replace authoritative
  memory, set `RepositoryLoadedV1`, or write either SaveGame slot.
- The exact Enhanced `BreakTransform` and `MakeTransform` forms are also
  harvested from a green compile and contract-tested. Unreal 5.6 represents
  Blueprint floating-point pins as precision subtypes and inserts supported
  float/double coercions at compile time; there is no separate global
  double-to-float action to discover. The document codec must prove every such
  coercion by compiling its real Transform/PlayFab connections and by
  round-tripping representative values through the executable codec oracle.
- No cooked `.pak` or Steam Workshop item exists. GitHub source cannot be added
  directly to G-Portal.

### Exact next autonomous slice

The next implementation sequence deliberately proves the complete backend through
keyboard controls, debug geometry, typed logs, and direct programmatic PIE calls
before any polished editor UI or cook is attempted:

1. **Complete:** freeze and version the persistent Flypath envelope, metadata,
   owner identity, visibility, revision, attribution, published snapshot,
   structural integrity mode, codecs, and live Blueprint validation contracts.
2. **Complete:** record-granular corrupt-newest fallback, duplicate ambiguity,
   generation-aware tombstone masking, and failure-guarded authoritative commit
   are accepted on the deterministic A/B recovery order.
   `EncodeWaypointV1`, `EncodeSegmentV1`, `EncodeDocumentV1`, all three matching
   document decoders, all three record encoders, all three record decoders,
   repository core, and exact numeric/null/type JSON node forms are accepted
   live-compiled proof, not remaining discovery work.
3. **Complete:** the inactive-slot writer creates a typed snapshot, writes it
   uncommitted, rewrites the same slot committed, and promotes authority only
   after both saves succeed. Generated full/paste graphs, exact initial and
   post-compile Unreal exports, marked compile/save, cold load, and a real
   two-process Blueprint SaveGame round trip all pass. The executable probe
   changes authority from generation 41 to 42, verifies the exact committed
   Unicode payload in a fresh process, and removes its isolated fixture.
4. **Complete:** private owner-only load, private-by-default create,
   owner-only optimistic `SaveDraftV1`, owner-filtered `ListMineV1`, and
   owner-only optimistic `DeleteFlypathV1` are
   accepted. Save replaces exactly one
   candidate envelope through the two-phase writer, advances only from the
   stored revision, preserves immutable metadata, publishes results only after
   physical commit, and survives fresh-process recovery/resumed writing. List
   is deterministic, metadata-only, read-only, owner-filtered, paged, and
   independently proven after SaveGame restart. Delete writes an ordered
   tombstone, removes aligned derived state only after physical commit, survives
   a fresh-process recovery, and completes a second generation-4/slot-B delete.
5. **Complete for publication control:** owner-only optimistic `PublishDraftV1` promotes
   a validated private draft to a public immutable snapshot without advancing
   the draft revision. It preserves the prior published snapshot across draft
   edits, republishes only the caller's expected draft revision, commits through
   the accepted A/B writer, survives a fresh process, and exposes only typed
   conflict state on rejection. `UnpublishV1` reverses only discoverability:
   it makes the record private while retaining the immutable published snapshot
   and draft history, uses the same owner/revision boundary and A/B writer, and
   survives fresh recovery plus resumed publish/unpublish writes.
6. **Complete for discovery:** `ListPublicV1` exposes only bounded metadata
   for records whose derived and decoded visibility are both public. It reuses
   the accepted deterministic `(updatedUtc, flypathId)` ordering and paging,
   clamps limits to 1..100, atomically rejects selected-record corruption or
   index disagreement, never decodes private rows, performs no writes, and
   preserves the same result after a fresh SaveGame recovery.
7. **Complete for playback fetch:** `FetchPublishedRevisionV1` returns only a
   validated immutable published document and its revision. Private rows are
   indistinguishable from missing rows, `0` selects the latest published
   revision, a positive revision must match exactly, negative revisions fail
   validation, and every path is read-only. Exact compiled-graph, live runtime,
   fresh SaveGame restart, stale-payload reset, cleanup, and cold-load evidence
   pass.
8. **Current:** add private cloning with immutable source attribution. Extend
   corruption recovery, limits, migration hooks, and typed failures across the
   final sharing boundary.
9. Implement the complete trajectory compiler: linear and cinematic curves,
   monotonic timing/speed profiles, smooth quaternion rotation, flight profiles,
   deterministic sampling, and discontinuity diagnostics.
10. Implement lens/focus/effect tracks, Directed/Free Look/Carrier Freecam, and
   event tracks with bounded target adapters and authorization.
11. Expose every backend operation through temporary shortcuts, compact debug
   displays, path geometry, and stable logs; cover success, rejection, boundary,
   reconnect, restart, cancellation, and restoration cases in programmatic PIE.
12. Run an attended end-to-end keyboard/debug dogfood pass. Only after that pass
   may polished library/editor/timeline UX begin.
13. Cook/package only after the full backend prototype and its dogfood workflow
   are accepted. Workshop and G-Portal remain later deployment gates.
14. Close, sync, run the complete repository suite, commit, and push after every
   meaningful compiled feature milestone.

### UX investment gate

The current product surface is intentionally shortcuts, path-preview geometry,
and diagnostic logs. No timeline, inspector, curve editor, or flypath library UI
is authorized by implementation momentum alone. UX work begins only after the
complete backend described above passes structural contracts, programmatic PIE,
and an attended keyboard/debug dogfood pass. The first UX prototype must solve
problems observed during that testing and stay small enough to discard or reshape
cheaply. Cooked-client and hosted-server gates do not block backend implementation;
they validate the integrated product after the backend milestone.

The shortcut-extension preparation sequence, run from the repository root after
copying the complete live EventGraph, is:

```powershell
$liveEvent = Join-Path $env:REDLEAF_SCRATCH_DIR 'client-event-live.eddgraph'
$editEvent = Join-Path $env:REDLEAF_SCRATCH_DIR 'client-event-k-r-delete.eddgraph'

.\tools\blueprint\Export-BlueprintGraphClipboard.ps1 `
  -DestinationPath $liveEvent
python .\tools\blueprint\Build-ClientWaypointEditDispatch.py `
  --input $liveEvent --output $editEvent
.\tools\blueprint\Test-BlueprintGraphSnippet.ps1 -Path $editEvent
python .\tools\blueprint\Test-WaypointCaptureContracts.py `
  --capture .\tools\blueprint\snippets\capture-current-waypoint.eddgraph `
  --event $editEvent
.\tools\blueprint\Set-BlueprintGraphClipboard.ps1 -SnippetPath $editEvent
```

After paste/compile/save, copy the complete live EventGraph again and substitute
that round-trip export for `$editEvent` in both validators. The generated file
passing before paste is necessary but not sufficient.

### Near-term test gates

- **Automated backend gate:** every module has structural contracts plus
  programmatic PIE acceptance that proves real state changes and edge cases.
- **Hands-on backend dogfood gate:** Laurent can create, edit, save, load,
  publish, discover, play, clone, retime, change curve/lens/event parameters,
  inspect debug state, hide/restore all HUD, and exit safely using shortcuts.
- **Polished UX gate:** only the accepted backend workflow is exposed through a
  coherent library/editor interface; the backend remains independently testable.
- **Cooked local single-player gate:** the complete accepted backend and UX load
  from a packaged mod, survive relaunch, and preserve all safety guarantees.
- **Hosted multiplayer gate:** the cooked build repeats ownership, privacy,
  snapshot, cloning, authorization, and restoration tests with two real clients.

## 2. Engineering rules

- Build Blueprint assets only inside the official Enhanced DevKit.
- Keep all mod-owned assets under `Content/Mods/ExileDroneDirector`.
- Never edit or relocate base-game assets; attach components through the Mod
  Controller and subclass/reference supported classes.
- Sync closed-editor `.uasset` source back to the Git repository after each
  verified slice.
- Test both PIE and cooked mod behavior; PIE success alone is insufficient.
- Test on a dedicated server as soon as the first RPC exists.
- Keep authoring data, compiled trajectory data, and UI state separate.
- Never use display name as ownership authority.
- Never add a smoothness feature without a discontinuity/scrub test.
- Never enter a camera state without a tested restoration path.

## 3. Phase 0 — DevKit reconnaissance and project creation

### Objectives

Confirm the Enhanced-specific integration points and create the real mod asset
root.

### Tasks

1. Complete and verify the DevKit installation.
2. Launch the DevKit and create `ExileDroneDirector` through its mod menu.
3. Record exact generated paths and Mod Controller conventions.
4. Identify candidate player controller, player character, HUD, game state,
   game mode, and server-owned persistence hosts.
5. Inspect component attachment rules for Client, Server, and Server and Client
   Copies.
6. Identify available input system and safe custom-action strategy.
7. Confirm camera, Cine Camera, post-process, SaveGame, GUID, quaternion, spline,
   and file/runtime rendering nodes exposed to Blueprint.
8. Identify the durable authenticated account/player ID exposed server-side.
9. Create a findings document with exact asset paths, screenshots, and rejected
   alternatives.

### Verification

- Mod loads in PIE with a visible diagnostic message.
- Cooked empty mod loads in local game without modifying a base asset.
- Client and dedicated-server component BeginPlay can be distinguished in logs.
- The repository's sync tool recognizes the actual DevKit layout.

### Exit gate

The project cooks, loads, and has confirmed client/server attachment candidates.

## 3.1 UI technology and design-system spike

This bounded spike begins immediately after the empty mod cooks; it does not wait
for the full-editor phase.

### Objectives

Prove that the Enhanced DevKit exposes the UMG painting, focus, pooling, and input
hooks needed for a polished production timeline and establish the shared theme
before one-off widgets proliferate.

### Tasks

1. Create central theme/token assets using the palette, type, spacing, shape,
   motion, track, and state definitions in `docs/visual-design-system.md`.
2. Build production candidates for button, numeric field, slider, panel, icon,
   tooltip, track row, key, Cue, and State Clip components.
3. Prototype the responsive viewport/list/inspector/timeline workspace.
4. Demonstrate adaptive timeline grid/ruler, pan/zoom, playhead scrub, batched
   curve drawing, pooled key/clip dragging, and context-inspector switching.
5. Prove text focus does not leak drone/timeline shortcuts and Emergency Exit
   remains reachable.
6. Measure at 1080p, 1440p, 4K, ultrawide, and representative UI scales.

### Exit gate

The interaction foundation meets its frame-time budget, scales correctly, and
passes the initial visual QA checklist using mock data. These widgets become the
production component library rather than a disposable mockup.

## 4. Phase 1 — Safe local camera vertical slice

### Objectives

Enter Drone Mode, move a local camera, and restore the game perfectly.

### Assets

- `BP_EDD_ModController`
- `BPC_EDD_ClientDirector`
- `BP_EDD_DroneCamera`
- `WBP_EDD_DroneHUD`
- Initial state/input enums and settings struct

### Tasks

1. Attach the client director only to the owning local player context.
2. Implement the client state machine: Inactive, Entering, Flying, Restoring.
3. Cache original pawn, view target, input mode, cursor, HUD state, and movement
   policy.
4. Spawn a non-replicated camera actor and call local view-target switching.
5. Implement six-axis movement, mouse look, speed trim, normal/fine/boost modes,
   and optional horizon lock.
6. Separate camera input from carrier motion so the same controller can support
   Directed, Free Look, and Carrier Freecam modes during later playback.
7. Keep the player pawn physically unchanged and never change possession. Drive
   the non-replicated local drone with explicit delta-time transform integration,
   and restore only the cached view target on exit.
8. Implement idempotent Emergency Exit.
9. Bind restoration to death, pawn replacement, teleport, disconnect, UI close,
   camera destruction, and component end-play.
10. Add an opt-in collision sweep and diagnostic HUD.

Current vertical-slice progress: tasks 1, 4, and 7 are proven in a two-player
listen-server PIE fixture. Each director gates input by owning-local-controller
identity; host and remote client create non-replicated local drones, move them
independently at the expected 600 units/second, retain their original controlled
pawns, and restore their exact prior view targets. Task 5 has proven W/S, D/A,
and E/Q translation and now contains compiled local mouse-look dispatch using
raw mouse delta, configurable sensitivity, inverted pitch, and zero roll. Host
yaw plus host/client world isolation were observed in PIE; hands-on client
pitch/yaw feel remains pending because the automation layer cannot inject raw
mouse input into the detached preview. Speed trim, precision, and boost are now
implemented as a separate named contract: proportional 1.25x wheel trim,
30-6000 clamp, 0.25x Ctrl precision, 3x Shift boost, precision precedence, and
delta-time `FInterpTo` smoothing. Host and remote-client runtime checks proved
baseline, easing, target speeds, movement-distance ordering, isolation, and
exact F9 restoration. Physical-wheel feel remains a hands-on gate. Smooth
horizon lock is now compiled and runtime-proven: H toggles it, held C/Z wins,
disabled lock preserves bank, and enabled lock eases toward explicit world up
without changing current pitch/yaw. Host/client isolation and exact F9
restoration were re-proven with the completed 33-node function.
Task 8 is proven idempotent through F9, and camera destruction within task 9 is
proven through the active-camera validity guard. Death, teleport, disconnect,
UI-close, component-end-play, dedicated-server, and cooked-runtime acceptance
remain explicit gates.

### Test matrix

- Single-player PIE
- Listen server as host and client
- Dedicated server with two clients
- Enter/exit ten consecutive times
- Exit while moving and while UI has keyboard focus
- Die/respawn, teleport, disconnect, and close UI while active
- Destroy camera actor artificially
- Reload mod/session and verify normal Conan camera/input

### Exit gate

The cooked mod can fly for ten minutes and survives every restoration test without
moving the pawn, losing input, retaining a cursor/HUD override, or duplicating a
camera actor.

## 5. Phase 2 — Local Flypath authoring core

### Objectives

Create an in-memory private Flypath and edit intentional waypoints.

### Assets

- `ST_EDD_FlypathDocument`
- `ST_EDD_Waypoint`
- `ST_EDD_Segment`
- `BP_EDD_PathPreview`
- Editor command/undo structs
- Expanded `WBP_EDD_Editor`

### Tasks

1. Implement stable IDs for waypoints, segments, and editor commands.
2. Capture current drone position, body/gimbal rotation, basic focal length/FOV,
   and focus distance into a waypoint.
3. Append, insert, replace, duplicate, reorder, and delete waypoints.
4. Jump the editor camera to a selected waypoint without moving the pawn.
5. Provide exact numeric transform editing plus WASD/mouse fine adjustment.
6. Render numbered markers and a linear path preview.
7. Implement transactional undo/redo for all waypoint operations. The bounded
   history core, capture/replace/delete transaction boundaries, physical
   shortcuts, stable logs, live 64-entry cap, redo-branch invalidation, and PIE
   runtime acceptance are complete. Normal cooked-client acceptance remains.
8. Implement structural validation and clear diagnostics.
9. Keep draft model independent from preview actor components.

Current vertical-slice progress: task 1 now has a stable monotonic waypoint ID
source, and the append/replace/delete core is implemented and runtime-proven.
`CaptureCurrentWaypoint` snapshots the local drone transform plus focal length,
aperture, manual focus distance, and zero hold time into six temporary lockstep
arrays owned only by `BPC_EDD_ClientDirector`; it selects the appended index and
advances the ID only after every channel append completes.
`ReplaceSelectedWaypoint` preserves the stable ID and hold while replacing the
five camera-state channels at a valid selection. `DeleteSelectedWaypoint`
removes all six channels atomically and clamps selection to the surviving item
or `-1`. These arrays remain the explicit transitional runtime model while the
new typed bridge is integrated; they are not the final server document. All
three live graphs have semantic pin-level contracts.
A deterministic two-player edit cycle proved two captures, lens/transform
replacement, middle/end/empty deletion behavior, invalid-index no-op behavior,
remote-client isolation, exact pawn/view restoration, and restoration of the
drone class defaults. The reviewed K/R/Delete dispatch and shared dynamic
count/selection feedback are live in the 51-node EventGraph. Real keyboard input
passed after the one-time PIE character was saved, and the complete compiled
graph now round-trips into the checked-in textual source with capture, edit, and
feedback contracts.

The version-1 document oracle is also complete. It gives the Blueprint data
assets a tested target contract before runtime migration. Executable tests
cover canonical round-trip serialization, exact-field and semantic-corruption rejection,
finite and normalized camera state, ID/topology validation, private creation,
optimistic saves, immutable publication, private deep clones, attribution, and
owner/viewer access. Runtime save/load is not claimed until the Blueprint
adapter and server persistence layer consume this contract.

The first mapping step is live: `ST_EDD_Waypoint` has Integer `WaypointId`,
Transform `CameraTransform`, and Float `FocalLength`, `Aperture`,
`ManualFocusDistance`, and `HoldSeconds`. `SyncDraftWaypointsV1` now performs a
guarded structural migration from the six legacy channels into
`DraftWaypointsV1`. It validates every channel length, positive unique IDs, and
the complete finite/scalar camera domain before clearing the prior typed
snapshot, then maps one indexed value from every channel into each struct. The
complete 84-node/362-pin graph compiles green, round-trips with reciprocal links,
and passed production-path PIE for empty, exact two-waypoint, idempotent, and
restoration behavior. Capture/edit dispatch calls it on every successful
mutation, making the typed array the authoritative read-side document snapshot
while the legacy arrays remain temporary write-side channels.

The first visible preview slice is also live. `RebuildPreviewV1` consumes the
accepted `ST_EDD_FlypathDocument` directly, clears both HISM pools before every
evaluation, stops cleanly when preview is disabled, and adds one ordered
world-space marker for every typed waypoint. A three-phase PIE harness uses the
real capture/document pipeline to seed one and then two waypoints into fresh
preview actors. It proves exact instance transforms and counts, confirms the
segment pool stays empty in the marker-only slice, exercises one-to-zero and two-to-zero
clears, restores class defaults, and removes every temporary editor actor. The
next step is the independently contract-tested linear segment loop, followed by
client-owned spawn/update/teardown wiring.

### Verification

- Author twenty waypoints and edit the middle ten.
- Undo/redo the full operation chain without changing IDs/order incorrectly.
- Delete and reinsert endpoints.
- Feed invalid/NaN-equivalent values through UI boundaries and reject them.
- Maintain acceptable editor frame time with the initial maximum waypoint count.

### Exit gate

A creator can compose and revise a local multi-waypoint Flypath reliably, and its
document can be serialized/deserialized in memory without loss.

## 6. Phase 3 — Trajectory compiler v1

### Objectives

Produce deterministic, scrub-safe playback with linear, manual cubic, and smooth
cinematic trajectories.

### Assets

- Trajectory compiler Blueprint/function library
- Compiled segment/sample structs
- Arc-length table implementation
- Time-profile curve assets/presets
- Trajectory diagnostics

### Tasks

1. Define the compiled Flypath representation and engine version `1`.
2. Implement Linear spatial segments.
3. Implement cubic Hermite/Bezier with generated and manual tangents.
4. Implement quintic position interpolation with shared position, velocity, and
   acceleration boundary constraints for C2 cinematic continuity.
5. Implement Stop, Glide, Fly-by, Tight, and Cut corner modes.
6. Build adaptive arc-length tables and distance-to-parameter inversion.
   The validated inversion primitive is accepted; deterministic adaptive table
   construction and route integration remain.
7. Implement monotonic Linear, Smoothstep, Smootherstep, and Cinematic S-curve
   time profiles.
8. Implement duration and target-speed modes plus impossible-constraint warnings.
9. Sample curves for overshoot, collision, duration, and continuity diagnostics.
10. Make evaluation a pure function of compiled data and absolute time.

### Verification

- Constant-speed test over unequal curved segments.
- Direct scrub to arbitrary time equals forward playback result.
- Position is exact at required interpolating waypoints.
- Numeric derivative probes show expected C0/C1/C2 continuity.
- No curve loop/overshoot with standard auto presets on adversarial waypoint sets.
- Linear and Cut remain deliberately discontinuous only where requested.
- Identical document and engine version produce identical sampled outputs.

### Exit gate

The editor plays and scrubs linear, manual, and C2 cinematic paths with stable
timing and actionable diagnostics.

## 7. Phase 4 — Rotation, flight profiles, and deterministic drone character

### Objectives

Separate airframe and gimbal and deliver Cinematic, Hybrid, and FPV identities.

### Tasks

1. Normalize and sign-align serialized rotations.
2. Implement quaternion multi-key interpolation using SQUAD or a Blueprint-safe
   equivalent with smooth angular velocity.
3. Implement Cinematic airframe tangent/look-ahead orientation and clamped
   curvature-derived banking.
4. Implement independent gimbal orientation, horizon lock, fixed look-at, and
   weighted body-lock.
5. Implement Hybrid stabilization as a continuous blend.
6. Build deterministic FPV compilation with gates, acceleration/turn limits,
   bank/pitch derivation, camera uptilt, and fixed-timestep prebaking.
7. Add Cinewhoop, Freestyle, Long-range, Cinematic, and Hybrid presets.
8. Add deterministic coherent wind/vibration tracks with stored seeds.
9. Add a minimum-snap/seventh-order spike; adopt only if Blueprint solve cost and
   numerical stability beat the quintic system meaningfully.

### Verification

- No quaternion long-way flips or Euler wrap artifacts.
- Angular velocity does not visibly jump at smooth waypoint boundaries.
- Scrubbing produces stable body/gimbal transforms.
- FPV playback is identical at different game frame rates.
- Presets produce observably distinct behavior from identical waypoints.
- Procedural motion repeats exactly and blends in/out continuously.

### Exit gate

One waypoint layout can be replayed convincingly as stabilized cinematic,
body-expressive hybrid, and momentum-driven FPV without reauthoring positions.

## 8. Phase 5 — Camera, lens, focus, and visual tracks

### Objectives

Turn trajectory playback into authored cinematography.

### Tasks

1. Confirm cooked Cine Camera/post-process property availability.
2. Implement the common scalar-track evaluator and curve presets.
3. Add focal length, filmback, aperture, focus distance, focus influence,
   exposure EV, and effect blend-weight tracks.
4. Implement manual focus, Set Focus Here trace, fixed focus marker, rack focus,
   and smoothed fixed-target autofocus.
5. Add linear-distance and reciprocal-distance/diopter focus interpolation.
6. Visualize focal plane and approximate depth-of-field range in editor.
7. Add dolly-zoom authoring helper.
8. Add supported bloom, vignette, grading/tint, motion blur, chromatic aberration,
   sharpening, matte, and other verified effect tracks.
9. Build named base looks without hiding individual values.
10. Implement viewer comfort overrides for roll, shake, blur, exposure changes,
    and chromatic aberration.

### Verification

- Every continuous scalar track passes value/derivative boundary probes.
- Focus and focal-length pulls scrub and replay identically.
- Dolly zoom keeps the selected fixed subject approximately constant in frame.
- Unsupported cooked properties fail as unavailable, not as broken controls.
- Comfort overrides are local and do not mutate the Flypath document.

### Exit gate

A creator can author a smooth lens/focus/effect sequence aligned with movement,
and another viewer can safely reduce comfort-sensitive effects.

## 9. Phase 6 — Server repository, identity, and private drafts

### Objectives

Persist owner-editable private Flypaths across dedicated-server restarts.

### Tasks

1. Complete storage-adapter spike and select the supported server persistence
   mechanism.
2. Implement server repository and metadata index.
3. Resolve durable authenticated account identity.
4. Implement server policy and validation limits.
5. Implement Create, List Mine, Fetch Draft, Save Draft, Rename, and Delete.
6. Add optimistic concurrency and typed errors.
7. Add debounced save, retry/backoff, offline-change state, and save-as-new conflict
   recovery.
8. Add schema/version serialization and first migration harness.
9. Add bounded rate limiting and server logs.

### Verification

- Create/save/reconnect/reload private Flypath.
- Restart dedicated server and recover identical data/ownership.
- Attempt update/delete from a second account and receive Forbidden.
- Open same path in two sessions and exercise RevisionConflict.
- Corrupt/incompletely write a test candidate and recover previous committed data.
- Exceed every configured limit and receive a safe typed failure.

### Exit gate

Private Flypaths are durable, server-authoritative, owner-protected, and
recoverable.

## 10. Phase 7 — Publishing, discovery, playback, and cloning

### Objectives

Complete the social Flypath loop.

### Tasks

1. Implement atomic Publish Draft and Unpublish.
2. Implement paged My Flypaths and Server Flypaths metadata queries.
3. Implement published snapshot fetch/cache by ID and immutable revision; add a
   digest only if a supported native Blueprint seam becomes available.
4. Implement library search/filter/sort and compatibility badges.
5. Implement individual viewer playback preparation, countdown, controls, and
   safe restoration.
6. Implement Directed, Free Look, and Carrier Freecam playback modes with
   snap-free entry, recenter, return-to-directed, speed trim, and emergency exit.
7. Implement a stable twist-minimizing carrier frame plus world-aligned and
   body-relative operator controls.
8. Keep operator offsets local and outside published snapshot identity, event
   evaluation, and server authority.
9. Implement Clone Published as a deep private copy with attribution.
10. Ensure draft edits never mutate published revision.
11. Ensure republish never changes active playback snapshots.
12. Add administrative unpublish/delete and policy controls.
13. Add region/bounds compatibility checks.

### Two-client acceptance scenario

1. Player A creates and saves a private Flypath.
2. Player B cannot list or fetch it.
3. Player A publishes revision 1.
4. Player B discovers and begins revision 1 playback.
5. Player A edits the draft and publishes revision 2.
6. Player B finishes revision 1 unchanged.
7. Player B replays and receives revision 2.
8. Player B clones revision 2; clone is private and owned by B.
9. Player A edits/deletes the source; B's clone remains unchanged.

### Exit gate

The complete create/refine/publish/discover/play/clone/remix loop works on a
dedicated server with enforced privacy and immutable playback.

## 11. Phase 8 — Event tracks and world-interaction backend

### Objectives

Add safe local Cues and server-authorized State Clips without turning Flypaths
into an unrestricted remote-control mechanism.

### Tasks

1. Implement Event track, Cue, State Clip, target-binding, adapter, and compiled
   execution-plan structures from `docs/event-system.md`.
2. Implement local presentation Cues and deterministic Cue-crossing ledger.
3. Implement absolute-time State Clip evaluation and scrub-safe preview.
4. Build Bind Target viewport interaction and resolution diagnostics.
5. Implement EDD Event Anchor, then a narrow door adapter.
6. Ship `Wait Until Open` before any mutating door operation.
7. Add viewer-authorized interaction and typed server results.
8. Add bounded cinematic state leases only after cancellation, disconnect,
   conflict, and restoration tests pass.
9. Add publishing capability metadata, policy controls, rate limits, and clone
   binding disable/rebind behavior.

### Acceptance sequence

- Scrubbing across a Cue never executes a world action.
- Real playback fires each configured Cue exactly once per loop/direction policy.
- A door State Clip reaches open state before camera arrival or applies its
  explicit failure policy.
- Unauthorized viewers cannot change the door.
- Cancel/disconnect restores or safely yields leases without affecting camera
  restoration.
- A clone is private and cannot use the source world binding until reauthorized.

### Exit gate

Local Cues and one narrow door workflow operate predictably on a dedicated server
with explicit permission, failure, clone, and cleanup behavior.

## 12. Phase 9 — Full editor UI

### Objectives

Expose the already-proven backend through the library/editor/timeline workflow
described by the product design. This phase must not become a second backend.

### Tasks

1. Implement responsive editor layout with collapsible panels.
2. Build waypoint list, viewport overlays, and property inspector.
3. Build timeline travel/hold blocks and draggable playhead.
4. Add track visibility, key selection, key dragging, box selection, and retime.
5. Build curve editor with semantic presets and advanced tangent controls.
6. Add Smooth Selected/Everything with lock-aware transactions.
7. Add error/warning navigation to exact waypoint/segment/track.
8. Add remappable controls and prevent bindings while editing text.
9. Add dirty/saving/conflict/recovery status.
10. Add keyboard navigation and usable scaling at supported resolutions.

### Verification

- Repeat the accepted keyboard/debug workflows through the UI and compare the
  resulting documents, repository revisions, compiled paths, and typed results.
- Complete an authoring task using primarily mouse/UI.
- Repeat using primarily keyboard/drone controls.
- Undo/redo bulk retime and smoothing as single transactions.
- Resize/collapse panels without losing selection or active edit.
- Test input focus, text fields, sliders, curve handles, and Emergency Exit.

### Exit gate

A knowledgeable player can create and fine-tune a polished Flypath without
opening debug tools, while the independent shortcut/debug acceptance suite still
passes unchanged.

## 13. Phase 10 — Streaming, capture, and playback polish

### Objectives

Make real-world server playback and recording dependable.

### Tasks

1. Test camera-driven streaming at route extremes and different regions.
2. Implement route preparation/prewarming supported by Conan.
3. Add conservative bounds/speed policy where streaming cannot keep up.
4. Implement Clean Playback HUD suppression and configurable countdown.
   The suppression path uses the same remappable `Toggle Clean Frame` action as
   authoring/free flight and restores the exact prior native-HUD and overlay
   visibility state.
5. Document OBS and Steam Recording workflows.
6. Add loop, selection playback, and deterministic repeated takes.
7. Add optional authoring-pass capture that reduces live Free Look/Carrier
   Freecam operation into editable gimbal and carrier-offset keys.
8. Verify that pausing freezes the carrier while preserving live camera control.
9. Probe runtime Movie Render Pipeline and image/video outputs in cooked build.
10. Add direct rendering only behind an experimental flag if completely safe.
11. Investigate optional local thumbnail capture.

### Verification

- Long route, fast FPV route, dense build, dungeon/interior, and low-client-FPS
  cases.
- Cancel capture at every stage and restore UI/view.
- Repeated takes produce identical evaluated transforms.
- Remote recording never moves the player pawn.

### Exit gate

Clean external recording is reliable; direct rendering is either verified and
isolated or explicitly documented as unsupported.

## 14. Phase 11 — Release hardening

### Objectives

Ship a supportable public Workshop release.

### Tasks

1. Profile Blueprint CPU, allocations, preview component counts, network payloads,
   server storage, and load times.
2. Tune policy defaults and waypoint/key limits from measurements.
3. Complete schema migration and downgrade/future-version messages.
4. Test mod load order and known UI/input conflicts.
5. Validate installation/update on fresh client and dedicated server.
6. Write player guide, server-admin guide, privacy/PvP warning, troubleshooting,
   and recovery instructions.
7. Add in-mod version/build diagnostics.
8. Produce sample Flypaths covering cinematic, hybrid, FPV, orbit, rack focus,
   and dolly zoom.
9. Run a closed two-server beta before public Workshop publication.

### Exit gate

No critical camera-restoration, ownership, privacy, persistence, or corrupt-save
defects remain; public documentation matches actual cooked behavior.

## 15. Test strategy

### 15.1 Automated/math harnesses

Where Blueprint automation is available, build data-driven tests for:

- Curve endpoints and finite values
- C0/C1/C2/C3 derivative continuity expectations
- Arc-length constant-speed error tolerance
- Time-curve monotonicity
- Quaternion shortest path and angular continuity
- Deterministic procedural noise
- Serialization round-trip and migration
- Authorization decision tables
- Document bounds and validation

If the DevKit lacks a useful automation runner, expose deterministic editor
utility tests and golden sampled outputs that can be run before cooking.

### 15.2 Manual runtime matrix

- Single-player
- Listen server host/client
- Dedicated server with at least two accounts
- High/low frame rate
- Death/respawn
- Teleport and region transition
- Disconnect/reconnect
- Server restart
- Mod update/schema migration
- Dense player build and empty landscape
- Long cinematic and high-speed FPV paths
- Different UI scaling/resolutions and remapped controls

### 15.3 Release-blocking defect classes

- Player camera/input cannot be restored
- Player pawn moved/teleported unintentionally
- Unauthorized private data access or mutation
- Clone linked to or mutating its source
- Published revision changes during active playback
- Server persistence corruption or destructive migration
- Non-deterministic published trajectory at different frame rates
- Unbounded RPC/storage payload

## 16. Risk register and mitigation

| Risk | Impact | Mitigation/spike |
| --- | --- | --- |
| No clean dedicated-server mod persistence | Critical | Repository adapter spike; persisted actor or supported server SaveGame fallback |
| No durable Blueprint account ID | Critical | Inspect authenticated controller/player state; block sharing until authoritative identity exists |
| Camera view target does not drive streaming | High | Early remote-route spike; prewarm/bounds restrictions; same-region policy |
| Cine Camera/post-process stripped in cook | High | Cooked Phase 0/5 probes; fallback Camera component and supported properties |
| Blueprint global minimum-snap solve unstable | Medium | Ship quintic C2 first; precompute bounded systems; reserve seventh-order for verified cases |
| FPV integration depends on frame rate | High | Fixed-step compile/prebake and absolute-time sample evaluation |
| UMG curve editor too expensive/fragile | Medium | Semantic presets first; advanced editor built after core evaluator |
| Public Flypaths enable PvP scouting | High | Admin/creative defaults, range/region policy, explicit warnings |
| Large revisions overload RPC/storage | High | Limits, on-demand fetch, revision keys, full-document measurement before deltas |
| DevKit update moves private base members | Medium | Attachment adapters, minimal base coupling, version diagnostics |
| Enhanced cook/upload has no stable headless entry point | High | Prove the Funcom plugin commandlet; otherwise use a self-hosted Windows runner with a narrowly automated editor cook step |
| Workshop credentials or Steam Guard make unattended CI fragile | High | Create and accept the first item manually; keep secrets off Git; prefer an authenticated self-hosted runner and deliberate release approval |
| Direct video output unavailable | Low | External recording is the supported baseline |
| World events become a remote-control/PvP exploit | Critical | Typed adapters, server policy, revision validation, target binding, rate limits, clone rebind |
| Stateful event rollback overwrites concurrent changes | High | Adapter conflict detection, bounded leases, conservative yield, explicit persistent actions |
| Blueprint UMG timeline becomes slow/incoherent | High | Early production UI spike, batched drawing, pooling/virtualization, token/component enforcement |

## 17. Planned asset organization

```text
Content/Mods/ExileDroneDirector/
  BP_EDD_ModController
  Core/
    Client/
    Server/
    Camera/
    Validation/
  Data/
    Structs/
    Enums/
    Presets/
    Curves/
  Trajectory/
    Compiler/
    Evaluator/
    FlightProfiles/
    Diagnostics/
  Persistence/
    Repository/
    Adapters/
    Migration/
  UI/
    Library/
    Editor/
    Timeline/
    Playback/
    Settings/
    Style/
    Components/
  Events/
    Adapters/
    Bindings/
    Execution/
    Anchors/
  Debug/
  Tests/
```

## 18. Version roadmap

- **0.1 Camera Spike:** safe enter/fly/exit in cooked multiplayer.
- **0.2 Local Authoring:** waypoints, undo, linear and cinematic playback.
- **0.3 Drone Motion:** quaternion/gimbal, cinematic/hybrid/FPV profiles.
- **0.4 Camera Suite:** lens, focus, effects, and keyboard/debug editing.
- **0.5 Server Drafts:** identity, persistence, ownership, conflicts.
- **0.6 Sharing Alpha:** publish, library, viewer playback, cloning.
- **0.7 Directing Alpha:** local Cues, State Clips, bindings, and safe door adapter.
- **0.8 Editor Beta:** polished library, inspector, timeline, and curve UX.
- **0.9 Capture Beta:** streaming/capture polish, admin policy, migrations.
- **1.0 Public Release:** hardened complete loop and documentation.

Version numbers describe capability gates, not calendar promises.

Internal checkpoint versions such as `0.21.0-flypath-schema-bridge` count validated
development slices. They do not claim that the public **0.1 Camera Spike** gate
is complete; that gate still requires cooked multiplayer acceptance.

## 19. Immediate execution priority

The installation, camera foundation, typed draft/document sync, linear playback,
client-owned marker/linear-segment preview, bounded history transaction core,
and repeatable isolated PIE runner are complete. The immediate sequence is:

1. Keep `tools\Run-DraftHistoryPIE.ps1`, the full scaffold, and the cold asset
   gate green after every relevant change. Graph contracts own shortcut wiring;
   isolated PIE runners own runtime semantics and edge cases.
2. **Complete:** record-granular newest-to-older recovery on the accepted
   authority ordering and tombstone merge; authoritative memory is replaced
   only after the complete candidate remains valid.
3. **Complete:** the inactive-slot two-phase writer and modular private
   create/save/load/list/delete boundaries pass in-process and fresh-process
   SaveGame recovery acceptance.
4. **Complete for the sharing repository slice:** owner identity, private CRUD,
   immutable publication, bounded public discovery, immutable published fetch,
   and private deep clone with immutable source attribution are accepted with
   typed conflicts/limits/failures and fresh SaveGame recovery evidence.
5. Complete cinematic position/timing/rotation, flight profiles, lens/focus/
   effect tracks, free-look carrier modes, and event execution.
6. Give every operation a shortcut/debug route and run the complete automated
   and attended backend dogfood matrix.
7. Only then build the polished UI against those stable contracts.
8. Cook and deploy only after the complete backend and UI integration passes.

The first backend capability milestone is not “the camera moved in PIE.” It is
“all planned Flypath operations and cinematic tracks survived automated PIE and
attended keyboard/debug dogfooding without violating persistence, authority,
determinism, or restoration contracts.”

## 20. Definition of done for 1.0

The release is done when the product release criteria in the design specification
pass on a dedicated server, all release-blocking defect classes are cleared, the
server can restart without losing or exposing Flypaths, motion and camera tracks
remain smooth and deterministic, and a normal player can complete the full
creative/social loop without developer assistance.
