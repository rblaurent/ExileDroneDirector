# Exile Drone Director — Product and Interaction Design

Status: authoritative design direction for the first public release
Target: Conan Exiles Enhanced, private and community servers
Primary object: a server-persistent cinematic asset called a **Flypath**

## 1. Product vision

Exile Drone Director is an in-game cinematography system. It lets a player leave
their normal view, fly a virtual drone through the world, capture intentional
camera waypoints, refine the resulting motion and lens work, and publish the
finished Flypath to the current server. Other members of that server can discover
the Flypath, play it as a local cinematic experience, or clone it into a private
editable copy.

The core loop is:

**Fly → capture → refine → preview → publish → discover → experience → clone → remix**

The mod is not merely a free camera, a spline mover, or an external recording
button. Its value comes from combining a capable drone camera, a compact timeline
editor, durable server sharing, and deterministic playback into one coherent
creative tool.

## 2. Product principles

### 2.1 Author with the camera, not with coordinates

The primary way to create a Flypath is to fly the drone to a compelling frame and
capture it. Numeric editing, curve handles, and property panels refine an authored
shot; they do not replace the spatial act of composing it.

### 2.2 Smoothness is a system-wide property

Position is not the only animated value. Translation, body orientation, gimbal
orientation, speed, acceleration, banking, focal length, focus distance,
aperture, exposure, post-process weights, and transitions between flight styles
must all support continuous interpolation. The editor may intentionally create a
hard change, but accidental discontinuities are treated as defects.

### 2.3 Simple first, deep when requested

A creator should be able to capture three waypoints, select a Cinematic preset,
and obtain a convincing shot without understanding splines or jerk. Advanced mode
exposes tangents, continuity, speed envelopes, lens curves, banking, gimbal
behavior, and exact numeric values.

### 2.4 Publishing must be safe and predictable

New Flypaths are private. Clones are private. Public playback uses an immutable
published revision, never somebody's half-edited draft. Ownership and visibility
are enforced by the server rather than trusted to the client UI.

### 2.5 Playback must never strand the player

The player pawn remains possessed and physically present. Entering Drone Mode or
playback changes the local view target; it does not transform or possess the
character. Manual exit, death, teleport, region change, disconnect, errors, and
mod shutdown all restore normal camera, input, cursor, and HUD state.

### 2.6 A Flypath is a server-local cultural object

A public Flypath belongs to the server on which it was authored. It can document
a build, create a tour, stage a reveal, or become a shared template. Cross-server
export may be added later, but it must not weaken the ownership and privacy model
of the server library.

### 2.7 Remain a dedicated camera-path tool

Exile Drone Director does one job deeply: authoring, refining, sharing, and
experiencing camera Flypaths. It is not a general server-administration suite,
quest framework, actor puppeteer, building toolkit, or all-purpose visual
scripting system. World interaction exists only where it directly supports a
shot, through narrow typed event adapters. Integrations must not make unrelated
systems prerequisites for the core camera workflow.

## 3. Terminology

- **Flypath:** the editable cinematic asset and its revision history.
- **Draft:** the owner's current editable revision.
- **Published revision:** the immutable revision visible to other players.
- **Clone:** a deep private copy owned by the cloning player, with source
  attribution but no live link.
- **Waypoint:** an authored camera/drone state at a meaningful point in the shot.
- **Segment:** the travel interval from one waypoint to the next.
- **Spatial curve:** the geometric path followed by the drone.
- **Time profile:** the mapping from playback time to distance along the path.
- **Flight profile:** the rules that convert the authored path into drone-body
  and gimbal behavior.
- **Camera track:** lens, focus, exposure, and visual-effect animation.
- **Carrier:** the evaluated moving reference frame produced by the Flypath
  before live operator input is applied.
- **Operator override:** transient local free-look or six-axis input layered over
  the carrier during preview or playback.
- **Published snapshot:** the complete data downloaded for uninterrupted local
  playback.

## 4. Roles and permissions

### 4.1 Creator/owner

The owner can view, play, edit, rename, clone, publish, unpublish, and delete their
Flypath. Ownership is tied to a durable server/platform identity, not a mutable
character or display name.

### 4.2 Server member/viewer

A normal member can list and play published Flypaths, inspect public metadata,
and clone a published revision. They cannot update, publish, unpublish, or delete
the source Flypath.

### 4.3 Server administrator

An administrator can moderate public content, unpublish or delete abusive paths,
inspect ownership metadata, and configure global limits. Whether administrators
can open private content is an explicit server policy and should default to the
least surprising behavior documented to players.

### 4.4 Permission matrix

| Action | Owner: private | Owner: public | Other member | Administrator |
| --- | ---: | ---: | ---: | ---: |
| List metadata | Yes | Yes | Public only | Policy-controlled |
| Fetch full revision | Yes | Yes | Published only | Policy-controlled |
| Play | Yes | Yes | Published only | Yes |
| Edit draft | Yes | Yes | No | No by default |
| Publish changes | Yes | Yes | No | No by default |
| Clone | Yes | Yes | Published only | Published only |
| Unpublish | N/A | Yes | No | Yes |
| Delete | Yes | Yes | No | Yes |

## 5. Flypath lifecycle

### 5.1 Creation

Creating a Flypath produces a new server-issued Flypath ID, assigns the current
player as owner, creates the first draft, and sets visibility to private. The
creator supplies a name immediately or receives a timestamped temporary name.

### 5.2 Editing

All edits apply to the owner's draft. Saving is debounced and revision-aware.
Local edits remain recoverable while a server save is in flight. The interface
shows Saved, Saving, Offline Changes, Conflict, or Error rather than pretending
every edit succeeded.

### 5.3 Publishing

Publishing validates and atomically snapshots the draft. The new published
revision replaces the previously advertised revision only after the server has
stored it successfully. Existing viewers continue playing the snapshot they
already downloaded.

Editing a public Flypath does not expose unfinished changes. The library card can
show “Unpublished changes” to its owner.

### 5.4 Unpublishing

Unpublishing removes the Flypath from the server library without deleting its
draft or revision history. A viewer who already started playback may finish their
local snapshot unless a server-wide emergency revocation policy is later added.

### 5.5 Cloning

Cloning downloads the selected published revision and submits it as a new private
Flypath owned by the requester. It preserves source Flypath ID, source revision,
creator display name, and title for attribution. Later changes or deletion of the
source do not modify the clone.

### 5.6 Deletion

Owner deletion requires confirmation and removes the server's active Flypath.
Clones remain independent. Administrative deletion records a moderation reason
in server logs. Trash/recovery can be considered after persistence limits are
known.

## 6. Information architecture

The main UI has four top-level destinations:

1. **My Flypaths** — owned private and public paths, drafts, and clones.
2. **Server Flypaths** — published paths from all permitted creators.
3. **Editor** — live drone viewport, waypoint controls, inspector, and timeline.
4. **Settings** — controls, playback comfort, capture preferences, and creator
   defaults.

The active authoring session may be reopened without returning to the library.
Emergency Exit is always available through a dedicated key that is not consumed
by text fields or timeline focus.

## 7. Library design

### 7.1 Flypath cards

Each card presents:

- Name and optional thumbnail
- Creator display name
- Private/Public and Draft/Published status
- Duration and waypoint count
- Region/map
- Flight profile badge
- Created and last-published timestamps
- Clone attribution when applicable
- Compatibility or missing-content warning

Primary actions are Play, Edit for owners, Clone for published paths, and a
context menu for rename, publish, unpublish, duplicate, and delete.

### 7.2 Search and filtering

The server library supports search by title/creator and filters for region,
duration, flight profile, recently published, and compatible-with-current-region.
Sorting and paging occur over metadata; full trajectory payloads are fetched only
when needed.

### 7.3 Thumbnail policy

The first release may use a creator-selected screenshot if runtime image storage
is practical; otherwise it uses a generated profile/region card. Thumbnails are
strictly optional and must not block the core sharing system.

## 8. Editor workspace

The editor uses a four-region layout:

```text
┌ Flypath/Waypoints ┬──────── Live Drone Viewport ────────┬ Inspector ┐
│ library context   │ framing, gizmos, focus markers      │ values    │
├───────────────────┴──────────────────────────────────────┴───────────┤
│ Timeline: waypoints, segments, speed, body, gimbal, lens, effects   │
└──────────────────────────────────────────────────────────────────────┘
```

Panels can collapse so the live camera remains useful at different resolutions.
The viewport shows only authoring overlays; clean preview hides them all.

### 8.1 Drone navigation

Default flight controls provide forward/back, strafe, ascend/descend, yaw,
pitch, optional roll, and mouse-wheel speed trim. Precision modifiers are:

- Normal movement for composition
- Coarse/boost movement for travel
- Fine movement for centimeter-scale framing
- Optional local-space or world-space translation
- Optional horizon lock

Control bindings are remappable and must avoid silently replacing core Conan
bindings.

### 8.2 Capturing a waypoint

Capture records the current authored state: position, camera/body orientation,
lens state, focus state, hold settings, and relevant global-track keys. The
creator can insert after selection, append, replace the selected waypoint, or
duplicate it.

### 8.3 Waypoint selection and fine-tuning

Selecting a waypoint supports:

- Jump the editor camera to it
- Replace it with the current camera
- Nudge it with WASD/mouse using normal, coarse, or fine increments
- Move/rotate with viewport gizmos
- Edit exact numeric fields
- Modify values with sliders
- Change its arrival/corner behavior
- Reorder, duplicate, or delete it

Sliders always pair with numeric entry. Modifier keys adjust slider precision.
Undo/redo covers every authoring operation, including bulk smoothing and retime.

### 8.4 Segment editing

Selecting the interval between two waypoints exposes:

- Duration or target-speed authoring mode
- Spatial curve type
- Time/speed curve
- Flight-profile override
- Position, rotation, and scalar continuity
- Banking and gimbal response
- Collision behavior
- Visual-effect transitions

The editor previews changes immediately using a locally compiled trajectory.

## 9. Timeline and curve editing

### 9.1 Timeline behavior

The timeline displays waypoint markers, travel blocks, and hold blocks. Creators
can drag a waypoint in time, trim a hold, retime a segment, box-select keys, and
scale the duration of a selection or the entire Flypath.

Core playback controls are play/pause, stop, loop selection, jump to previous or
next waypoint, frame selection, and a draggable playhead. Scrubbing must evaluate
all stateless tracks consistently without requiring playback from time zero.

### 9.2 Tracks

The first complete editor supports:

- Position/trajectory
- Drone-body orientation
- Camera/gimbal orientation
- Speed/time profile
- Focal length
- Focus distance and focus influence
- Aperture
- Exposure compensation
- Post-process blend weights
- Procedural motion intensity
- Cues and State Clips for supported local and world interactions

Tracks may be hidden from the simple interface but remain part of the same
evaluation model.

### 9.3 Smoothing operations

Creators can apply Smooth Selected or Smooth Everything. Smoothing never means
“replace all keys with the same ease.” It resolves tangents and derivative
constraints across the affected channels while preserving locked values and
intentional cuts.

The normal UI offers semantic choices such as Linear, Soft, Cinematic, Tight,
Aggressive, Stop, Glide, Fly-by, and Cut. Advanced mode exposes tangents, custom
curves, derivative constraints, and continuity details.

## 10. Movement design

### 10.1 Three independent layers

Every segment is evaluated through three conceptually separate layers:

1. **Spatial path:** where the trajectory goes.
2. **Time profile:** how playback time advances over real distance.
3. **Flight profile:** how an airframe and mounted camera behave while following
   that trajectory.

This prevents geometry, speed, and camera personality from being incorrectly
collapsed into a single spline parameter.

### 10.2 Spatial curve choices

- **Linear:** exact straight travel; deliberately available for mechanical or
  cable-camera shots.
- **Auto Cinematic:** a minimum-jerk/minimum-snap interpolating trajectory that
  preserves smooth velocity, acceleration, and where practical jerk through
  waypoints.
- **Manual Bezier/Hermite:** explicit incoming/outgoing handles for authored
  curvature.
- **Smooth Control Curve:** a B-spline-like path for exceptionally smooth fly-by
  motion where control points influence rather than necessarily intersect the
  path.
- **Orbit/Arc:** analytic movement around a focus point.
- **Hold/Cut:** no travel or intentional discontinuity.

### 10.3 Timing and speed

Curves are reparameterized by approximate arc length so constant speed means
constant world-space speed. A monotonic time profile then controls acceleration,
braking, and speed emphasis. Presets include Constant, Ease, Cinematic S-curve,
Accelerate Through, Brake Into, and custom curves.

Creators can author either duration or desired speed. If configured acceleration,
turning, or jerk limits make the requested duration impossible, the editor warns
and offers to stretch time rather than silently violating the selected flight
profile.

### 10.4 Corner behavior

- **Stop:** arrive at zero speed, optionally hold, then depart.
- **Glide:** intersect the waypoint with smooth derivatives.
- **Fly-by:** preserve momentum and treat the waypoint as a gate/tolerance zone.
- **Tight:** reduce tangent magnitude to stay close to the point.
- **Snap turn:** preserve an intentional aggressive redirection.
- **Cut:** discontinuous camera edit rather than physical travel.

## 11. Flight profiles

### 11.1 Cinematic Drone

- Minimum-jerk/minimum-snap translation
- Jerk-limited acceleration and braking
- Horizon stabilization
- Limited configurable banking
- Independent three-axis gimbal
- Predictive look-ahead
- Smooth focus/lens response
- Optional low-frequency wind drift

### 11.2 FPV / Acro

- Waypoints behave primarily as flight gates
- Momentum, acceleration, and minimum-turn-radius constraints
- Body orientation derived from desired velocity and acceleration
- Visible pitch, bank, roll, and configurable camera uptilt
- Speed carried through corners
- Controlled overshoot and aggressive correction
- Cinewhoop, freestyle five-inch, and long-range starting presets

### 11.3 Hybrid

- Smooth authored trajectory
- Airframe banks into turns
- Gimbal partially compensates for body motion
- A continuous stabilization blend between body-locked FPV and fully stabilized
  cinematic framing

### 11.4 Airframe and gimbal separation

The drone body and camera are separate transforms. A cinematic airframe may bank
while its gimbal maintains level subject framing. An FPV camera remains mostly
body-locked and therefore exposes every dive and roll. The editor can visualize
both transforms without requiring a visible in-world drone model.

### 11.5 Procedural motion

Wind, motor vibration, and imperfect stabilization use deterministic,
band-limited coherent noise. Raw per-frame randomness is forbidden. Procedural
motion has amplitude, frequency, seed, and blend-weight tracks so it remains
repeatable and smoothly enters or exits.

## 12. Camera, lens, and visual design

### 12.1 Camera stack

The evaluated camera is layered in a stable order:

1. Base lens/look preset
2. Flypath-wide values
3. Segment and waypoint animation
4. Flight-profile body and gimbal behavior
5. Procedural motion
6. Viewer comfort/safety override

Every blendable layer exposes a continuous weight.

### 12.2 Lens properties

- Focal length using physical millimeter values
- Filmback/sensor preset
- Aperture/f-stop
- Focus distance
- Optional focus smoothing and breathing
- Aspect ratio and cinematic matte
- Motion blur controls where available

Focal length is the primary authored value; FOV is displayed as derived
information where possible. Dolly zoom couples camera distance and focal length
to preserve subject framing.

### 12.3 Focus modes

- **Manual distance** with slider and exact value
- **Set Focus Here** by viewport trace
- **Fixed world focus marker**
- **Track actor** when a stable runtime binding exists
- **Rack focus** between two fixed or bound subjects
- **Smoothed autofocus** with configurable response

The editor visualizes the focal plane and approximate near/far depth-of-field
limits. Focus pulls support linear-distance and optical/diopter interpolation.

### 12.4 Post-processing

Subject to cooked-runtime availability, tracks may control exposure compensation,
bloom, lens flare, vignette, saturation, contrast, color tint/grading, motion
blur, chromatic aberration, sharpening, and reusable look presets. Effects are
blended, not abruptly toggled.

Starting presets include Clean Cinematic, Epic Landscape, Dreamy Shallow Focus,
Dark Sorcery, High-Speed FPV, Vintage Lens, Documentary, and Raw.

### 12.5 Viewer comfort override

Players may locally reduce or disable roll, procedural shake, strong blur,
flashing exposure, chromatic aberration, and similar comfort-sensitive effects.
The override never alters the published Flypath. The player can always use the
emergency exit key.

## 13. Playback experience

Selecting Play fetches the published snapshot, checks schema and region
compatibility, precompiles trajectory data, optionally counts down, and switches
the local view target. The player body remains in the world and vulnerable unless
a server policy explicitly changes that rule.

Minimal playback controls are pause/resume, restart, optional scrub, comfort
override, and emergency exit. Authoring overlays are hidden. On completion or
cancel, the system restores the original view target and every cached input/UI
state.

### 13.1 Directed and interactive playback modes

Playback can remain completely authored or permit local live operation:

1. **Directed:** position, body, gimbal, lens, and effects follow the authored
   Flypath exactly.
2. **Free Look:** the Flypath continues to carry the camera, while mouse or
   controller input temporarily controls the gimbal/look direction.
3. **Carrier Freecam:** the Flypath acts as a moving rail or invisible carrier.
   The player has six-axis control over a local camera offset around it as well
   as unrestricted look control.

Free Look and Carrier Freecam are opt-in playback controls. Live input is local,
never changes the published snapshot, and is never replicated as an authoritative
world position. Entering an interactive mode blends from the authored camera to
the live offset without a snap. Recenter and return-to-directed commands blend
back to the authored transform; Emergency Exit always restores the Conan camera
immediately.

Carrier offsets use a stable transported path frame so spline curvature or drone
bank does not unexpectedly corkscrew the operator around the route. World-aligned
and body-relative controls may both be offered, with world-aligned as the comfort
default. A configurable soft tether prevents accidental loss of the route while
still allowing unrestricted freecam where server policy permits it.

During authoring, an operator pass may optionally be recorded into editable
gimbal and carrier-offset tracks. During ordinary viewing it remains ephemeral.
Pausing stops the carrier but leaves interactive camera control available for
inspection and reframing.

Playback is individual by default. Synchronized premieres, queued tours, or
forced server-wide playback are outside the first release.

## 14. Region, streaming, and world-change behavior

Every Flypath records its region/map identity and conservative spatial bounds.
The library warns when the viewer is outside a compatible region. The first
release should not silently teleport the character between regions.

Public Flypaths describe absolute world-space camera positions. Buildings and
actors may change after publication; the path remains valid but its composition
may no longer match. Optional anchor-relative Flypaths can be investigated later
only if stable server object identities are available.

Before playback, the client samples the route for collision and streaming risks.
Collision warnings do not silently rewrite a creator's published shot.

## 15. Server policy and PvP safety

A remote camera can reveal bases, defenses, and player activity. Server owners
must be able to configure:

- Who may create, publish, clone, or play Flypaths
- Whether private paths are visible to administrators
- Maximum Flypaths per owner/server
- Maximum waypoints, duration, and spatial extent
- Allowed regions and maximum camera distance from the character
- Whether the player body remains vulnerable
- Whether public playback is admin/creative-only
- Whether live actor tracking is allowed

Safe defaults favor single-player and cooperative/private servers. The mod must
not market unrestricted remote playback as suitable for competitive PvP.

## 16. Recording boundary

The dependable first-release workflow is clean deterministic playback captured
by OBS, Steam Recording, or another external recorder. The mod supplies countdown,
clean HUD, repeatable timing, and capture-safe restoration.

Direct Movie Render Queue or image-sequence output is a later technical spike and
is enabled only if Conan's cooked build ships the required runtime modules. It is
not allowed to delay the creator, sharing, or playback core.

## 17. Defaults

- New Flypath visibility: Private
- Clone visibility: Private
- Published playback: immutable snapshot
- Default flight profile: Cinematic Drone
- Default spatial curve: Auto Cinematic
- Default corner: Glide
- Player body: remains in world and vulnerable
- Collision: warn during authoring, do not alter published playback
- Region mismatch: block with explanation
- Comfort override: enabled and locally configurable
- Recording: external capture

## 18. Explicit non-goals for the first release

- Moving or teleporting the player pawn along the Flypath
- Unrestricted official-server use
- Cross-server cloud marketplace
- Multi-user simultaneous editing
- Full Unreal Sequencer parity
- Stable tracking of arbitrary transient actors
- Automatic collision-avoidance that changes composition
- Native MP4 encoding as a release blocker
- A required replicated physical drone actor

## 19. Product release criteria

The product direction is proven when a player can:

1. Create a private Flypath on a dedicated server.
2. Fly and capture several waypoints.
3. Refine motion, timing, gimbal, focus, and lens values without discontinuities.
4. Save, leave, reconnect, and recover the draft.
5. Publish an immutable revision.
6. Have another permitted player discover and play that revision.
7. Have that player clone it into a private independently editable Flypath.
8. Update the original draft and republish without disrupting active playback or
   mutating the clone.
9. Exit authoring/playback safely after completion, cancellation, death,
   teleport, disconnect, or an evaluation error.

That is the minimum complete creative and social loop. Additional effects and
flight presets deepen it; they do not substitute for it.

## 20. Event and visual-system extensions

The timeline supports typed one-shot **Cues** and interval-based **State Clips**.
They cover safe local presentation and, under explicit server authority, bound
world interactions such as waiting for or opening a door. Normal scrubbing never
fires irreversible world actions. Clones retain event structure but disable
world bindings until the new owner deliberately rebinds them. The complete
authoring, authority, lease, failure, and cloning rules are defined in
`docs/event-system.md`.

The complete UI follows the centralized system in
`docs/visual-design-system.md`. Its direction is a premium modern cinematography
tool expressed through Conan's charcoal, iron, bone, copper, ember, and blood
palette. Design tokens, shared components, progressive disclosure, batched
timeline rendering, explicit interaction states, accessibility, and visual QA are
release requirements. Functional but incoherent or ad hoc UMG screens do not
satisfy the product definition.
