# Exile Drone Director — Visual Design System

Status: authoritative UI quality and implementation specification
Direction: a modern professional cinematography tool expressed through Conan's palette

## 1. Design thesis

The interface should feel like a premium drone-planning and color/camera tool
that naturally belongs in the Hyborian world. It takes color, material restraint,
and atmosphere from Conan without turning every control into fantasy ornament.

The shorthand is:

**DaVinci Resolve or a premium drone application redesigned for the Hyborian Age.**

The UI is sleek, calm, legible, and coherent. Dense information appears only
where the task demands it. Conan influence lives in palette, subtle surface
treatment, typography accents, and angular construction—not decorative clutter.

## 2. Non-negotiable quality rules

- No arbitrary colors, spacing, radii, fonts, or animation durations inside
  individual widgets.
- No one-off button/slider/dropdown implementations when a system component
  exists.
- No random gradients, excessive glow, glassmorphism, fake parchment panels,
  ornamental skulls, rivets on every surface, or runes used as unlabeled controls.
- No emoji in the shipped UI.
- No color-only meaning.
- No inconsistent icon families or stroke weights.
- No hidden destructive action without confirmation and undo/recovery where
  appropriate.
- No animation that delays frequent editing actions.
- No screen ships without hover, focus, pressed, selected, disabled, loading,
  empty, warning, and error states where applicable.
- No screen is considered complete because its controls merely function.

## 3. Experience principles

### 3.1 Viewport first

The shot remains the primary object. Panels collapse, timeline height changes,
and inspectors become contextual so the live camera view retains useful space.

### 3.2 Progressive disclosure

The tool separates workflows:

- **Compose:** fly, frame, capture, select, and reorder waypoints.
- **Refine:** timing, curves, movement, body, gimbal, lens, and focus.
- **Direct:** Cues, State Clips, world bindings, titles, and effects.
- **Publish:** validation, metadata, visibility, compatibility, and preview.

Simple mode exposes semantic intent. Advanced mode exposes mathematical and
systems detail without changing the underlying document.

### 3.3 Context over control walls

Selection determines the inspector. A waypoint, segment, tangent, curve key,
camera key, Cue, State Clip, or Flypath each presents only relevant fields.

### 3.4 Precision without intimidation

Sliders pair with numeric input. Modifiers change adjustment precision. Direct
viewport manipulation, semantic presets, and sensible defaults handle common
work; exact values and curves remain one interaction away.

## 4. Design tokens

All visual values live in central theme/data assets. Widgets consume semantic
tokens rather than literal values. The initial values below are starting points
to validate against Conan gameplay footage, HDR/SDR, and actual game fonts.

### 4.1 Core color palette

| Token | Initial value | Use |
| --- | --- | --- |
| `Color.Canvas` | `#0E0D0C` | Full-screen/editor background |
| `Color.Surface.1` | `#151311` | Primary panels |
| `Color.Surface.2` | `#1C1916` | Raised panels/rows |
| `Color.Surface.3` | `#25211D` | Menus, selected elevation |
| `Color.Border.Subtle` | `#332E28` | Dividers and quiet outlines |
| `Color.Border.Strong` | `#4A4137` | Focused structure |
| `Color.Text.Primary` | `#E5DAC7` | Warm bone primary text |
| `Color.Text.Secondary` | `#A99E8D` | Secondary labels |
| `Color.Text.Muted` | `#746C61` | Disabled/metadata text |
| `Color.Accent.Copper` | `#B66A3C` | Primary action and movement |
| `Color.Accent.Ember` | `#D39A52` | Active selection/current time |
| `Color.Accent.Blood` | `#8E302C` | Destructive/critical action |
| `Color.Accent.Steel` | `#668493` | Lens/focus and informational state |
| `Color.Accent.VioletAsh` | `#796A86` | Effects/directing tracks |
| `Color.Success` | `#71835B` | Valid/saved/available |
| `Color.Warning` | `#C18A43` | Risk, unresolved compatibility |
| `Color.Error` | `#B84A42` | Error/invalid/failed |

Red is not the default accent. Blood-red is reserved for danger, destructive
actions, and high-severity state. Ember/copper carries selection and creative
action so the interface does not become a red-black gaming cliché.

### 4.2 Track palette

| Track | Token/color | Secondary encoding |
| --- | --- | --- |
| Waypoints/position | Copper | Solid path/diamond keys |
| Speed/time | Sand/Ember | Curved line/square keys |
| Airframe | Iron-red | Banked-axis icon |
| Gimbal | Gold | Camera-gimbal icon |
| Lens/focus | Steel-blue | Aperture/lens icon |
| Effects | Violet-ash | Layer icon |
| Local events | Bone | Hollow Cue marker |
| Viewer interactions | Copper | Hand/interaction icon |
| Server events | Blood outline | Server/lock icon |
| Warnings | Warning amber | Dashed outline |

Track identity always combines label, icon, shape/line style, and color.

### 4.3 Typography

Use a legible modern sans-serif for all controls, numeric values, timeline labels,
tooltips, and long text. A Conan-compatible display face may be referenced for
screen titles, Flypath hero titles, and rare section accents after cooked-font
availability and licensing are verified.

Suggested semantic scale at 100% UI scale:

| Token | Size/weight | Use |
| --- | --- | --- |
| `Type.Display` | 24–28, medium/display face | Library/editor title |
| `Type.Heading` | 18–20, semibold | Panel/page heading |
| `Type.Subheading` | 14–16, semibold | Section and track group |
| `Type.Body` | 13–14, regular | Controls and descriptions |
| `Type.Label` | 11–12, medium | Compact labels/metadata |
| `Type.Numeric` | 12–13, tabular | Timeline/time/property values |
| `Type.Caption` | 10–11, regular | Secondary metadata |

Numeric/time fields require tabular numerals. Uppercase is restricted to compact
category labels, never paragraphs.

### 4.4 Spacing and density

Use a 4-pixel base grid:

- `Space.1 = 4`
- `Space.2 = 8`
- `Space.3 = 12`
- `Space.4 = 16`
- `Space.5 = 24`
- `Space.6 = 32`

Compact timeline rows may use 28–32 px height. Normal controls use approximately
32–36 px. Primary actions may use 40 px. Hit targets remain comfortable even when
visual shapes are compact.

### 4.5 Shape and borders

- Corners are subtly angular: typically 2–4 px rather than pill-shaped.
- Pills are reserved for tags/status chips.
- Standard border is 1 px; active/focus may use 1–2 px plus restrained glow.
- Panel separation relies on tonal value and borders, not heavy drop shadows.
- Timeline clips may use clipped/angled leading edges for Conan character while
  remaining clear and modern.

### 4.6 Surface texture

A faint low-contrast metal/stone grain may appear on large static surfaces. It is
never placed behind dense text/curves, never animates, and never reduces contrast.
Most controls remain flat-tonal for precision.

### 4.7 Motion tokens

| Token | Duration | Use |
| --- | ---: | --- |
| `Motion.Instant` | 0–60 ms | Press/selection feedback |
| `Motion.Fast` | 120 ms | Hover, tooltip seed, small state change |
| `Motion.Standard` | 160 ms | Panel/tab transition |
| `Motion.Deliberate` | 220 ms | Modal/major workspace change |

Use restrained ease-out for entrances, ease-in for exits, and smooth symmetric
curves for reversible panel motion. No bounce/elastic animation in the editor.
Timeline dragging and scrubbing are immediate, never eased behind the pointer.

## 5. Component library

Every screen is composed from shared themed widgets.

### 5.1 Foundations

- Text styles
- Surface/panel
- Divider
- Icon
- Tooltip
- Focus ring
- Loading/progress state
- Empty/error state

### 5.2 Inputs

- Primary, secondary, quiet, destructive, and icon buttons
- Toggle, checkbox, radio/segmented control
- Text and search fields
- Numeric field with units, drag adjustment, and precision modifiers
- Slider plus numeric companion
- Dropdown/combobox
- Color/value curve control
- Keybinding recorder

### 5.3 Navigation and information

- Top workspace tabs
- Breadcrumb/context title
- Status chip
- Flypath card/list row
- Filter/sort bar
- Toast and persistent status banner
- Confirmation and conflict dialogs
- Validation issue row

### 5.4 Timeline/editor

- Track group header
- Track row
- Waypoint key
- Scalar/quaternion key
- Cue marker
- State Clip
- Playhead and range selection
- Curve/tangent handle
- Time ruler and grid
- Zoom/fit controls
- Mute/solo/lock/visibility buttons
- Viewport gizmo and focus marker

Components own their full interaction-state matrix. Screens do not reskin them ad
hoc.

## 6. Interaction states

Each interactive component defines:

- Default
- Hover
- Pressed
- Keyboard/controller focus
- Selected/current
- Disabled
- Read-only
- Loading/pending
- Success/saved
- Warning
- Error
- Conflict/unresolved

Focus is visible and stylistically consistent. Disabled state preserves readable
labels and explains its reason through tooltip/context rather than becoming
illegibly faint.

## 7. Workspace layout

### 7.1 Library

The library is calmer and more spacious than the editor. Flypath cards emphasize
title, thumbnail/region, creator, duration, flight profile, visibility, and
compatibility. Filters/search remain compact and persistent. Empty states teach
Create and Clone rather than displaying a blank panel.

### 7.2 Editor

```text
┌ Context/List ┬──────────── Live Viewport ─────────────┬ Inspector ┐
│ 240–300 px   │ flexible primary space                 │ 300–360px │
├──────────────┴─────────────────────────────────────────┴───────────┤
│ Timeline: collapsible, resizable, normally 240–360 px             │
└────────────────────────────────────────────────────────────────────┘
```

The left panel changes between waypoint list and track/directing context. The
right inspector follows selection. Both collapse independently. The timeline can
maximize for curve work and minimize for composition.

### 7.3 Timeline information hierarchy

Default collapsed groups:

1. Waypoints
2. Movement
3. Camera
4. Effects
5. Events

Expanding Movement reveals speed, airframe, and gimbal. Expanding Camera reveals
focal length, focus, aperture, and exposure. The user never sees every low-level
channel by default.

### 7.4 Direct mode

Direct mode foregrounds Event tracks and target binding while preserving the
viewport. Bound objects receive a restrained outline and label. Permission and
scope are visible before publication, not buried in an advanced dialog.

### 7.5 Playback HUD and operator modes

Playback defaults to a nearly clean frame. A compact transport strip appears on
input and fades when idle. It contains time/progress, pause, restart, a three-way
mode control for Directed, Free Look, and Carrier Freecam, Recenter, comfort
override, and Exit. The current mode is always named; it is never represented by
an unexplained camera icon alone.

Free Look shows a restrained gimbal-reticle state. Carrier Freecam additionally
shows offset distance, movement-speed tier, reference frame (World or Body), and
soft-tether proximity only while relevant. Recenter progress is communicated by
subtle motion/reticle convergence rather than a modal message. The HUD must be
fully suppressible for recording while Emergency Exit remains globally bound.

The suppression command is named `Toggle Clean Frame` everywhere: binding UI,
tooltips, logs, and documentation. It is not a panel-collapse shortcut. Clean
Frame hides Conan's native HUD and the complete mod-owned presentation layer in
one atomic state change, then restores each layer's previous visibility flag on
exit. Preview geometry is hidden, not rebuilt; no fade, toast, cursor, or focus
ring may contaminate the clean frame after the toggle completes. The toggle and
Emergency Exit remain operable without visible controls.

## 8. Timeline visual behavior

- Current time uses Ember and remains visible over every track color.
- Major/minor grid strength adapts to zoom.
- Selected keys/clips use outline plus luminance change, not color replacement.
- Hover reveals concise tooltips; inspector contains full parameters.
- Dragging shows exact time and snapping target.
- Invalid curves/events use dashed Error/Warning outlines and issue badges.
- Track mute/solo/lock states alter icon and line treatment.
- Curves are antialiased and drawn with consistent thickness.

The timeline must remain readable at both overview and frame-level zoom.

## 9. Visual states for sharing and events

Visibility/status language:

- Private: lock icon, neutral surface
- Public published: globe/server icon, Success accent
- Public with unpublished changes: published badge plus Ember draft dot
- Clone: branch/copy icon and source attribution
- Unresolved binding: broken-link icon and Warning treatment
- Server-world event: server/lock icon and Blood outline
- Admin-only: shield/lock icon and explanatory label

No state is communicated by red/green alone.

## 10. Accessibility and comfort

- Meet readable contrast targets against every surface token.
- Never rely on hue alone; combine text/icon/shape/pattern.
- Support Conan UI scaling and test 1080p, 1440p, 4K, and ultrawide.
- Preserve keyboard focus order and controller navigation where practical.
- Provide reduced UI motion independently of camera comfort settings.
- Use scalable text and avoid critical information inside texture/detail.
- Tooltips do not contain actions required to operate the UI.
- Destructive buttons are spatially separated from primary non-destructive action.

## 11. UMG implementation architecture

### 11.1 Theme/data assets

Create central Blueprint-accessible theme assets/structs for:

- Color tokens
- Typography styles
- Spacing/density
- Shape/border styles
- Icon references
- Motion timings/easing
- Track semantic styles
- Component state styles

Widgets query tokens through one theme service/style library. Literal style
values inside screen widgets are treated as review failures.

### 11.2 Timeline rendering

Do not instantiate UMG widgets for every grid line, curve sample, or off-screen
key. Use:

- Batched/custom painting for grids, curves, range shading, and static guides
- Pooled widgets for visible interactive keys, handles, Cues, and State Clips
- Virtualized/paged rows for long libraries and track lists
- One authoritative time-to-screen transform for draw, hit test, snapping, zoom,
  and pan
- Dirty-region/affected-track updates rather than full reconstruction per edit

Confirm the precise custom-paint hooks exposed by the Enhanced DevKit during the
UI technology spike.

### 11.3 View-model separation

Screen widgets bind to UI view models supplied by the Client Director. They issue
editor commands rather than mutating actors or server records directly. This
keeps selection, transient hover, expansion, and theme state out of Flypath data.

### 11.4 Input/focus

The editor has one explicit focus router for game/drone input, viewport gestures,
timeline shortcuts, text entry, modal dialogs, and Emergency Exit. Text fields
must never leak WASD shortcuts. Emergency Exit remains available above ordinary
widget focus.

## 12. Early UI technology prototype

The UMG interaction foundation is tested before the full editor waits until a
late polish phase. The prototype must demonstrate:

1. Responsive four-region workspace
2. Theme token application and live theme debugging
3. Timeline pan/zoom and adaptive ruler/grid
4. Playhead scrubbing
5. Selection and dragging of pooled keys and clips
6. Batched curve drawing and tangent handles
7. Track expansion/virtualization
8. Context inspector switching
9. Keyboard/text focus and Emergency Exit
10. 1080p/1440p/4K scaling and performance

This prototype may use mock Flypath data, but its widgets become production
components rather than throwaway screenshots.

## 13. Design workflow

For each screen/component:

1. Define job, hierarchy, and states.
2. Produce low-fidelity wireframe against real data density.
3. Apply tokens/component library.
4. Build UMG implementation.
5. Test keyboard/mouse/controller focus as applicable.
6. Test empty/loading/error/conflict/long-text states.
7. Capture at target resolutions over representative Conan scenes.
8. Review against visual QA checklist.
9. Only then mark the screen/component complete.

## 14. Visual QA checklist

- Uses only approved tokens/components
- Clear primary action and selection
- Consistent spacing/alignment on 4-pixel grid
- Correct typography hierarchy and tabular numeric values
- Complete interaction/error/loading states
- No color-only communication
- Adequate contrast over all surfaces
- No clipped text at supported scales
- Icon family/stroke is consistent
- Animation uses approved timing/easing
- Viewport remains primary where appropriate
- Dense timeline remains legible at overview and zoom
- Conan character is present but restrained
- Screenshot looks intentionally designed, not assembled widget-by-widget

## 15. Explicit anti-patterns

- Per-screen copies of button styles
- Direct hex colors inside arbitrary Widget Blueprints
- Full-width bright-red primary buttons
- Parchment texture behind timeline data
- Neon track rainbow unrelated to Conan palette
- Tiny unlabeled icons as the only discoverability path
- More than one inspector for the same selection
- Modals for adjustments that should preview live
- Hidden precision controls without numeric entry
- Rebuilding the entire timeline every Tick
- Animated background particles or distracting ambient ornament
- Inconsistent capitalization, punctuation, or unit formatting
- Placeholder programmer labels surviving into release

## 16. Release quality gate

The UI is release-ready when a new user can create, refine, publish, discover,
play, and clone a Flypath without developer explanation; an advanced user can
reach precise curves/events without fighting the simple interface; every screen
passes the visual QA checklist; timeline performance meets budget; and the whole
application appears to come from one design system.

Functional but incoherent UI does not pass this gate.
