# MVP backlog

## Spike 0 -- Enhanced DevKit integration

- Install and launch the Conan Exiles Enhanced DevKit.
- Create the `ExileDroneDirector` mod through the DevKit UI.
- Identify the correct client-side player/controller class for component
  attachment.
- Confirm that a spawned Blueprint camera actor can become the local view target
  and reliably return to the player.
- Confirm which input system Conan Enhanced exposes to cooked mods.

**Exit criterion:** one key enters an empty local camera and one key returns to
the unchanged player character in PIE and a cooked local test.

## Slice 1 -- Manual drone flight

- Implement `BP_EDD_ModController`, `BPC_EDD_DroneDirector`, and
  `BP_EDD_DroneCamera`.
- Add six-axis movement, mouse look, three speed bands, and speed trim.
- Add optional sphere-sweep collision.
- Add a minimal status HUD.
- Force camera restoration on every relevant end-play path.

**Acceptance:** fly for five minutes, collide with terrain, change speed, exit,
re-enter, die/respawn, and exit again without losing normal controls or camera.

## Slice 2 -- Waypoints

- Create `ST_EDD_Waypoint` and the director's ordered waypoint array.
- Capture the current transform and FOV.
- Select, replace, insert, and delete points.
- Teleport only the drone camera to a selected point for editing.
- Draw numbered waypoint markers.

**Acceptance:** author at least ten waypoints, revise the middle three, and retain
the correct ordering for the current session.

## Slice 3 -- Smoothed playback

- Generate automatic Hermite tangents.
- Implement explicit travel and hold durations.
- Evaluate position, rotation, look-at, and FOV independently.
- Add play, pause, scrub-step, loop, and stop.
- Sample the curve for collision warnings and permit linear fallback per segment.

**Acceptance:** repeatedly play the same route with stable timing, no rotational
wrap, no uncontrolled spline overshoot, and a clean return to edit mode.

## Slice 4 -- Recording pass

- Add a configurable countdown.
- Hide all mod preview geometry and chosen HUD layers.
- Lock editing input during playback while preserving an emergency stop key.
- Restore every hidden UI element after completion or cancellation.
- Document OBS/Steam Recording capture setup.

**Acceptance:** record a complete clean pass, cancel a second pass halfway, and
finish with the normal player camera/UI in both cases.

## Phase 2 -- Editor and persistence

- Draggable UMG timeline with segment blocks and holds.
- Numeric waypoint inspector.
- Manual positional tangent handles.
- Named routes, duplicate/delete, versioned SaveGame persistence.
- Fixed point, actor, and two-target composition modes.
- Dolly zoom and per-segment lens controls.
- Optional manual-flight sampling and keyframe reduction.

## Technical spikes after MVP

- Determine whether Movie Render Queue runtime Blueprints survive Conan's cook.
- Test image-sequence output location and permissions.
- Test world/region streaming behavior on long or fast routes.
- Decide whether a replicated cosmetic drone is worth its server and PvP costs.
