# Architecture

## Design rules

1. **Client-owned camera:** camera operation and route authoring stay on the
   owning client. No free-camera transform is replicated to the server in the
   MVP.
2. **Do not possess the drone:** the normal player pawn remains possessed. The
   local player controller switches its view target to a spawned camera actor.
   This avoids disrupting character ownership, movement replication, and server
   expectations.
3. **Always restore state:** every exit path restores the original view target,
   input mode, cursor state, HUD visibility, and any movement lock applied by
   the mod.
4. **Intentional keyframes:** the MVP stores authored waypoints rather than
   sampling every frame of manual flight.
5. **Separate translation and aim:** position follows a spatial curve while
   rotation/FOV use their own interpolation. This prevents spline tangents from
   accidentally controlling the shot's aim.

## Planned assets

### `BP_EDD_ModController`

The Conan mod entry point. It attaches `BPC_EDD_DroneDirector` as a client copy
to the most appropriate local-player host class exposed by the Enhanced DevKit.
The exact host class must be confirmed in-editor because Enhanced reorganized
several base-game assets.

### `BPC_EDD_DroneDirector`

The session coordinator and state machine.

States:

- `Inactive`
- `Flying`
- `Editing`
- `Previewing`
- `CleanPlayback`
- `Restoring`

Responsibilities:

- Validate local permission and spawn `BP_EDD_DroneCamera`.
- Cache the original view target and UI/input state.
- Enter and leave Drone Mode idempotently.
- Own the ordered waypoint array.
- Build/rebuild the path preview.
- Advance playback time and evaluate the route.
- Guarantee restoration on manual exit, death, teleport, disconnect, and
  component end-play.

### `BP_EDD_DroneCamera`

A local actor containing:

- Scene root
- Small collision sphere used for optional movement sweeps
- Camera component (Cine Camera only if its runtime dependency is confirmed)
- Optional debug mesh, disabled during clean playback

The actor receives normalized movement/look commands from the director. Initial
movement is six-axis noclip with optional collision:

- Forward/back and strafe
- Ascend/descend
- Mouse yaw/pitch
- Roll controls as a later option
- Precision, normal, and boost speed bands
- Mouse-wheel speed trim

### `ST_EDD_Waypoint`

Blueprint struct fields for the first implementation:

| Field | Type | Purpose |
| --- | --- | --- |
| `Transform` | Transform | Camera position and authored orientation |
| `FieldOfView` | Float | Lens framing at the waypoint |
| `TravelSeconds` | Float | Time from the previous waypoint |
| `HoldSeconds` | Float | Pause on this waypoint |
| `PositionEase` | Enum | Linear, smooth, ease-in, ease-out, ease-in-out |
| `RotationEase` | Enum | Independent aim interpolation |
| `bUseLookAtPoint` | Bool | Enable a fixed focus target |
| `LookAtPoint` | Vector | Persistent world-space focus point |
| `bCollisionEnabled` | Bool | Collision policy for the incoming segment |

Actor references are excluded from the saved MVP format because they are not
stable across sessions. Live actor tracking can be layered on later.

### `BP_EDD_PathPreview`

Owns a spline for positional visualization only. It renders waypoint markers,
the sampled curve, incoming-segment warnings, and the selected point. Playback
must not blindly use distance-along-spline for timing: each segment has an
explicit duration and easing function.

For the first smoothing implementation use cubic Hermite interpolation with
automatically generated tangents. Catmull-Rom-style auto tangents can overshoot
near walls, so every segment is sampled with collision sweeps and can fall back
to linear interpolation. Manual tangent handles belong in the polished editor.

### `WBP_EDD_DroneHUD`

The minimal authoring overlay:

- Current mode and flight speed
- Waypoint count and selected waypoint
- Add, replace, delete, previous, and next actions
- Preview/stop and clean playback controls
- Current route time and total duration
- Safety/permission and collision warnings

A full draggable timeline is Phase 2. The MVP proves camera control and route
evaluation before investing in complex UMG interaction.

## Camera evaluation

For a playback time `t`:

1. Resolve the active hold or travel segment from cumulative segment durations.
2. Normalize local segment time to `alpha` in `[0, 1]`.
3. Apply the segment's position easing to its Hermite curve.
4. Interpolate authored rotation separately using shortest-path quaternion
   interpolation and the rotation easing value.
5. If look-at is active, derive aim from the interpolated camera position toward
   the interpolated/fixed look-at point.
6. Interpolate FOV independently.
7. Apply the evaluated transform to the camera actor.

Position, rotation, and lens therefore remain editable without corrupting one
another.

## Recording boundary

The MVP provides deterministic clean playback, countdown, HUD hiding, and a
recording-state indicator. Actual capture uses OBS, Steam Recording, or another
external recorder so live actors, effects, and audio are preserved.

After the MVP, inspect the Enhanced DevKit and cooked client for the Movie Render
Pipeline runtime subsystem. Only build direct image/video output if the required
modules are already shipped and callable from cooked Blueprint assets.

## Multiplayer and safety

- Drone Mode is client-only and intended for single-player/private servers.
- The default policy leaves the character body in the world and vulnerable.
- Server-admin/creative-mode gating should be added before public release.
- Route transforms must never drive the player pawn or grant teleportation.
- A future visible drone is a separate replicated cosmetic actor; it must not be
  required for camera operation.
- Switching regions, teleporting, death, or disconnect forces `Restoring`.

## Persistence

Phase 1 routes live only for the current session. Phase 2 introduces a Blueprint
SaveGame object containing route name, map/region identity, waypoint data,
format version, and creation/update timestamps. Save migrations must preserve
older routes when waypoint fields evolve.
