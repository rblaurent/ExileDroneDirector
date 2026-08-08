# Exile Drone Director — Events and World Interaction

Status: authoritative extension of the product and technical architecture
Purpose: timeline-driven cinematic interaction without unsafe or ambiguous world mutation

## 1. Intent

Flypaths need to choreograph more than a camera. A door may open before the drone
passes through it, torches may ignite down a corridor, a subtitle may introduce a
location, or a modded mechanism may trigger on a precise beat. These behaviors are
represented by timeline **Cues** and **State Clips**.

Events are deliberately separate from continuous animation tracks:

- A continuous track evaluates a value at every time, such as focal length or
  banking intensity.
- A Cue represents a one-shot occurrence when playback crosses a time.
- A State Clip represents a desired state over an interval and can therefore be
  evaluated while scrubbing or seeking.

The system must preserve server authority, object ownership, cloning safety,
repeatable playback, and the fact that normal Flypath playback is an individual
local experience inside a shared multiplayer world.

## 2. User-facing concepts

### 2.1 Cues

Cues appear as icons/markers on an Event track and may perform actions such as:

- Request interaction with a door or supported object
- Trigger a mod-defined mechanism/channel
- Play a local sound
- Display a title, subtitle, or annotation
- Emit a recording marker
- Start a local cinematic effect
- Send a signal to another approved mod integration
- Trigger a supported actor animation or emote

A Cue defines forward/reverse behavior, repeat policy, scope, failure policy, and
permission requirements.

### 2.2 State Clips

State Clips appear as draggable timeline blocks and describe a state over time:

```text
Main Gate       ├──────── Open ────────┤
Courtyard Lamps      ├──────── Lit ───────────┤
Local Fog                  ├── Enabled ──┤
```

State Clips are preferred for doors, lights, looping effects, and other stateful
objects because seeking directly into the clip has a defined result. A pair of
unrelated Open and Close Cues does not provide the same guarantee.

### 2.3 Event tracks

The timeline can contain multiple named Event tracks grouped by target or purpose:

- World Objects
- Local Presentation
- Titles/Subtitles
- Sound
- Recording Markers
- Advanced/Integration

Simple mode shows semantic clip names and icons. Advanced mode exposes execution
scope, retry/timeout, rollback, and binding diagnostics.

## 3. Authoring workflow

### 3.1 Binding a target

1. Add an Object Event track.
2. Choose **Bind Target**.
3. Aim the drone/editor camera at a supported object.
4. Confirm the highlighted target.
5. Choose one of the actions/states advertised by its adapter.
6. Place and size the Cue or State Clip.

The viewport displays target highlight, friendly name, ownership/permission
status, binding stability, and supported operations. Unsupported objects cannot
be forced into a generic interaction path.

### 3.2 Door example

A creator binds `Main Gate`, chooses `Door State`, and drags an `Open` clip from
4.2s to 9.8s. The inspector offers:

- Execution scope
- Start/end lead time
- Wait for confirmation
- Timeout
- Failure policy
- Restore/lease behavior
- Required permission
- Preview policy

The path compiler checks that the drone reaches the opening after the door has
enough time to animate.

### 3.3 Preview

Scrubbing never fires irreversible shared-world Cues. Local presentation Cues may
preview when explicitly enabled. State Clips display their predicted state and
may use a safe local/editor preview adapter.

Real execution occurs only during a started playback session with a validated
event execution plan.

## 4. Execution scopes

Every Cue/State Clip has one explicit scope.

### 4.1 Local Cinematic

Runs only for the viewing client and may control subtitles, overlays, local audio,
recording markers, local visual effects, or other non-authoritative presentation.
This is the default and safest scope.

### 4.2 Viewer Interaction

The viewing client requests a normal permitted interaction. The server validates
the viewer's identity, object binding, distance/range policy, object ownership,
and Flypath event policy. Failure does not become success merely because the
camera is close to the target.

### 4.3 Server World Event

The server changes shared state for all players. This scope is disabled by default
and requires server policy plus owner/admin approval. It is appropriate for a
controlled cooperative machinima server, not unrestricted public PvP playback.

### 4.4 Synchronized Performance

A later mode in which one server-authoritative performance session owns the
timeline clock and executes each world event once while multiple clients watch.
Normal individual playback must not emulate this by letting every viewer fire the
same world event independently.

## 5. Failure policies

Each event selects one policy:

- **Continue:** record failure and keep playing.
- **Pause and Retry:** pause at the event, retry with backoff until timeout.
- **Wait for State:** pause until the target reports the required state.
- **Skip:** mark skipped and continue without retry.
- **Abort Playback:** restore camera/UI and end the session.
- **Prompt Viewer:** pause and offer Retry, Skip, or Exit when appropriate.

Default policies are safe and visible. A failed door interaction must never cause
the drone to blindly clip through a closed door unless the Flypath explicitly
allows collisionless continuation.

## 6. Door-specific policies

The first door adapter should support:

- **Wait Until Open:** read-only gate; another player/operator may open it.
- **Request Normal Interaction:** act using the viewer's normal authorization.
- **Cinematic State Lease:** temporarily request an open state and restore the
  prior state on completion/cancel, subject to conflict rules.
- **Persistent World Action:** intentionally open/close without rollback;
  administrator-only by default.

A camera's proximity is not equivalent to the character's normal interaction
range. Any broader range is an explicit server policy with a clear PvP warning.

## 7. Target binding

### 7.1 Binding abstraction

Serialized Flypaths must never store a transient actor pointer. `TargetBinding`
logically contains:

| Field | Purpose |
| --- | --- |
| `BindingType` | Stable object ID, Event Anchor, tag/channel, or query |
| `PersistentObjectId` | Conan-exposed durable placed-object identity when available |
| `RegionId` | Prevent cross-region accidental resolution |
| `ExpectedClass/Adapter` | Required supported interaction contract |
| `FallbackTransform` | Diagnostic/rebinding aid, not sole authority by default |
| `OwnerAtBindTime` | Informational audit value |
| `DisplayLabel` | Presentation only |
| `BindingVersion` | Migration/adapter compatibility |

### 7.2 Event Anchor fallback

If Conan does not expose reliable IDs for relevant placed objects, the mod can
provide an `EDD Event Anchor` placeable. The anchor owns a stable mod identity and
binds an approved action channel to a nearby/specified target. Flypaths reference
the anchor rather than attempting fragile transform-only discovery.

Anchors require owner/admin permissions and expose only explicitly configured
operations. They do not become a generic remote-control bypass.

### 7.3 Resolution

Before publication and playback, the server resolves bindings and reports:

- Resolved
- Missing
- Ambiguous
- Adapter unavailable
- Permission denied
- Region mismatch
- Object changed

The library can mark a published Flypath as partially incompatible without
downloading every payload.

## 8. Adapter model

World objects participate through an adapter/contract rather than a giant type
switch in the timeline.

An adapter provides:

- Supported Cue and State operations
- Parameter schema and editor labels
- Read-current-state function
- Server validation function
- Execute/apply function
- Optional restore function
- Capability and binding version
- Permission/range requirements

Initial adapters should remain narrow:

1. Door open/closed state
2. EDD Event Anchor channel
3. Local presentation events
4. Recording marker

Lights, elevators, traps, emotes, weather, and third-party integrations are added
only after their server semantics are explicit.

## 9. Event data model

### 9.1 Cue

| Field | Purpose |
| --- | --- |
| `EventId` | Stable identity within revision |
| `TimeSeconds` | Timeline position |
| `EventType` | Adapter-defined operation |
| `TargetBinding` | Optional target |
| `Parameters` | Validated operation payload |
| `Scope` | Local, ViewerInteraction, ServerWorld, Synchronized |
| `DirectionPolicy` | Forward, reverse, both, or reverse undo |
| `RepeatPolicy` | Once per session, every loop, manual reset |
| `FailurePolicy` | Continue, wait, retry, prompt, abort |
| `TimeoutSeconds` | Bounded wait/retry duration |
| `PermissionPolicy` | Required server rule/capability |

### 9.2 State Clip

| Field | Purpose |
| --- | --- |
| `ClipId` | Stable identity |
| `StartTime` / `EndTime` | Active interval |
| `DesiredState` | Adapter-defined state payload |
| `Enter/ExitLeadSeconds` | Account for physical animation time |
| `Scope` | Execution scope |
| `RestorePolicy` | None, restore captured, adapter default |
| `ConflictPolicy` | Yield, pause, abort, or admin override |
| `TargetBinding` | Required target |
| `Failure/Timeout` | Behavior when state cannot be reached |

### 9.3 Event track

Tracks store stable ID, label, color token, mute/solo state for editing, adapter
category, ordered Cues, and ordered State Clips. Publication strips purely local
editor selection/collapse state.

## 10. Compilation and execution plan

The Flypath compiler validates events and produces an event execution plan:

1. Resolve/validate track schema and adapter versions.
2. Sort Cues deterministically and reject duplicate IDs.
3. Validate State Clip ranges and target conflicts.
4. Resolve permissions and mark runtime-dependent conditions.
5. Calculate lead times and warn about camera/object timing conflicts.
6. Build a state interval index for absolute-time evaluation.
7. Build a Cue crossing index for forward/reverse playback.
8. Produce diagnostics and compatibility summary.

The plan remains separate from the camera trajectory so a missing optional local
subtitle does not invalidate spatial playback, while a required closed door may.

## 11. Cue crossing ledger

During real playback the session ledger records `(EventId, LoopIteration,
Direction)` executions. Advancing from time A to B queries every Cue crossed in
deterministic order and applies its repeat policy. Frame drops cannot skip Cues,
and oscillating around a timestamp cannot double-fire them unintentionally.

Seeking/scrubbing updates predicted State Clips but does not execute shared-world
Cues. Starting real playback after a seek creates/reconciles an execution plan
from the chosen time.

## 12. State leases and restoration

A Cinematic State Lease is server-owned and identified by playback session,
target, clip, requester, and expiry. It captures the adapter-readable initial
state, requests the desired state, and releases/restores on clip end, playback
cancel, disconnect, timeout, or server cleanup.

Restoration must not blindly overwrite a legitimate concurrent change. Each
adapter defines conflict detection. Conservative default behavior yields the
lease and logs a conflict rather than forcing the old state.

Leases are optional and limited. Objects without reliable state reads/restores do
not advertise lease support.

## 13. Server authority and RPC flow

For Viewer Interaction and Server World scopes:

1. Client starts playback with an immutable published revision/hash.
2. Server validates revision/event availability and creates an optional bounded
   event session token.
3. At the scheduled crossing or clip transition, the client submits Event ID,
   revision, session token, and expected target binding.
4. Server resolves identity, policy, adapter, binding, rate limit, current state,
   and event timing tolerance.
5. Server executes or returns a typed result.
6. Client applies the event's failure policy.

The client does not submit an arbitrary class/function name or unbounded payload.
Only operations present in the validated published revision and registered
adapter are executable.

## 14. Privacy, publishing, and cloning

Publication validates every binding and records required capabilities in library
metadata. Server owners may prohibit publishing world-mutating scopes entirely.

Cloning copies timeline structure and local presentation Cues. World bindings and
mutating scopes become **Disabled/Requires Rebind** by default, even on the same
server. The new owner explicitly confirms a target and permissions before
republishing. Source attribution is retained.

Private Flypath event payloads follow the same authorization as all other private
revision data.

## 15. Individual playback versus synchronized performance

Individual public playback is the core release behavior. Local events work
normally. Viewer interactions execute using the viewer's authorization. Server
world events are normally blocked or tightly policy-controlled because multiple
viewers have independent clocks.

Synchronized Performance is a later explicit mode with:

- One server-authoritative session and clock
- One execution of each world event
- Invited/opted-in viewers
- Readiness/loading phase
- Host controls for start/pause/abort
- Shared failure policy

It must not be accidentally implied by normal Play.

## 16. UI and visual language

- Cues use compact, consistent icons and semantic labels.
- State Clips use rounded/angular timeline blocks with clear active intervals.
- Local, Viewer, Server, and Synchronized scopes have distinct iconography and
  line treatment; color is not the sole distinction.
- Invalid/unbound targets show a broken-link state and direct Rebind action.
- Permission-required events show a lock/admin indicator before publication.
- The inspector uses adapter-provided fields built from the shared component
  system, never ad hoc per-event styling.

## 17. Server policy

Configurable limits include:

- Allowed scopes by role
- Allowed adapters/operations
- Maximum Event tracks, Cues, and State Clips per Flypath
- Interaction range and region rules
- Lease duration and concurrent lease limit
- Playback event session rate limits
- Whether public Flypaths may contain unresolved/optional events
- Whether administrators may approve an event-bearing revision

PvP-safe defaults disable Server World events and remote interactions.

## 18. Failure and cleanup requirements

- Event failure cannot prevent camera restoration.
- Playback cancellation releases leases and invalidates event session tokens.
- Disconnect/server restart expires sessions and performs best-effort cleanup.
- Missing targets are reported before playback where possible.
- Adapter exceptions/errors return typed failures; they never execute arbitrary
  fallback interaction.
- Timers/retries are bounded.
- Event logs include IDs/results without exposing private payloads unnecessarily.

## 19. Implementation sequence

1. Local presentation Cue track and execution ledger.
2. State Clip absolute-time evaluation with a local test adapter.
3. Target-binding UI and binding abstraction.
4. EDD Event Anchor adapter.
5. Read-only `Wait Until Open` door gate.
6. Viewer-authorized door interaction.
7. Optional cinematic state lease after conflict/restoration tests.
8. Publishing metadata, clone stripping/rebind, and server policies.
9. Third-party adapter extension contract.
10. Synchronized Performance only after core sharing is stable.

## 20. Acceptance scenarios

### Door fly-through

The creator binds a permitted door, authors an Open State Clip, previews without
mutating the live server while scrubbing, publishes, and plays. The door reaches
open state before the camera arrives. Canceling releases/restores according to
policy and always restores the camera.

### Unauthorized viewer

A viewer lacking door permission plays the route. Preflight reports the blocked
event. The configured policy pauses/prompts or skips; the server state is not
changed.

### Clone

A viewer clones the published route. The clone is private, the door binding is
disabled and marked Requires Rebind, and playing the clone cannot control the
source creator's door.

### Multiple viewers

Two viewers independently play a public path. Local events occur independently.
Server-mutating events obey policy/rate/session rules and cannot multiply into an
unbounded open/close storm.

### Scrub and loop

Dragging across a Cue never fires it. Real forward playback fires exactly once per
configured loop. Entering the middle of a State Clip calculates the desired state
without replaying every prior frame.
