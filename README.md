# Playblast Frames 2.0.2

Maya tool for capturing single-frame playblasts of a character from many shot
cameras at once, each camera at its own frame.

Only the character's geometry and the camera's image plane are drawn. For each
queued camera it writes up to three 4K viewport images, one per pass ticked in
**Passes**:

| Pass | File | What it shows |
| --- | --- | --- |
| Wireframe | `<prefix>_<camera>_wire.png` | Character wireframe over the plate. The character wears a useBackground shader, so its surface shows the plate but still hides back-facing wires |
| Shaded | `<prefix>_<camera>_wireOnShaded.png` | Wireframe on default grey lambert, over the plate |
| Material | `<prefix>_<camera>_material.png` | The character's own shaders and textures, over the plate |

`<prefix>` is optional and is left off entirely when the field is blank.

Every image is burnt in along the bottom with the rig name, the camera and the
pass, for example `hero_rig  |  cam080  |  Wireframe on Shaded`.

All passes are captured with Viewport 2.0 anti-aliasing at its maximum (16x
multisampling plus line anti-aliasing), whatever the scene is set to.

Requires Maya 2025 or newer (PySide6). No other install - the burn-in is drawn
with Qt, which Maya already ships, so there is no encoder to bundle.

## Install

Drag `install.py` into a Maya viewport.

It copies the `playblast_frames` folder into `<user app dir>/scripts`, adds a
**PBFrames** button to the current shelf, and opens the tool.

To open it later, use the shelf button or run:

```python
import playblast_frames
playblast_frames.show()
```

## Use

1. **Scene cameras** lists every camera in the scene except Maya's startup
   cameras (persp, top, front, side). Hit **Refresh** after opening a new scene
   or importing cameras.
2. Type in the search field to filter the list. Matching is fuzzy - with cameras
   named `camera001` to `camera200`, typing `080` finds `camera080`.
3. Select one or more cameras and hit **Add** (or double-click a single one) to
   queue them. **Add all** queues everything the current search is showing, and
   Enter in the search field does the same. Repeat with different searches to
   build up the queue; **Remove** and **Clear** edit it.
4. Each queued camera has a **Frame**. Cameras are added at the time slider's
   current frame; edit the number to change it, or scrub the time slider,
   select rows and hit **Set to current frame**.
5. Select the character's geometry in Maya - its top group, or individual
   meshes - and hit **Set from selection** beside **Character geometry**.
6. Tick the **Passes** to write. At least one stays ticked.
7. **Wireframe colour** sets the one colour every character wire is drawn in,
   in every pass that shows wires. Click the swatch to pick one. Untick to
   leave the scene's own wireframe colours alone.
8. Optionally set a **Filename prefix**. It goes in front of every filename, so
   a prefix of `both_models` with a camera called `face_cam` writes
   `both_models_face_cam_wire.png`. Leave it blank for no prefix.
9. Set **Output folder** - type a path or hit **Browse...**. It is created if it
   does not exist yet.
10. Hit **Process**.

The summary line above the button shows how many cameras are queued, how many
images that produces and the resolution being captured, and warns when no
character geometry is set.

Capturing changes nothing in the scene: the wireframe colour and the
useBackground shader are applied inside one undo chunk and undone when the
batch finishes, and your selection is put back.

## The camera queue file

The queue is written to a JSON file beside the scene, named after it -
`sh010_anim_v012.ma` gets `sh010_anim_v012_playblast_cams.json`. The path is
shown under the two lists in the window. It holds the character geometry and
each camera with its frame, so it can be read, edited or diffed outside Maya:

```json
{
  "character": [
    "|rig_grp|hero_rig:geo_grp"
  ],
  "cameras": [
    {"camera": "|rig_grp|hero_rig:cam080", "frame": 1012},
    {"camera": "|rig_grp|hero_rig:cam081", "frame": 1040}
  ]
}
```

It is saved every time the queue, a frame or the character changes, and loaded
when the tool opens, so the cameras, frames and character chosen for a shot come
back with that shot and survive a prefs reset. An unsaved scene has nothing to
sit beside, so its queue goes to `playblast_frames_untitled_cams.json` in the
Maya prefs folder until the scene is saved.

On open, saved cameras and character nodes are matched back to the current
scene by name, so re-opening a shot restores its queue even if the full DAG
paths changed. Anything not in the current scene is simply not restored.
Loading never writes back, and hitting **Refresh** in a scene missing those
cameras does not wipe the file either - opening the tool before a reference has
loaded cannot cost you the queue.

Queue files from 1.x (a plain list of cameras) still load; their cameras come
in at the current frame.

The output path, filename prefix, passes and wireframe colour are Maya
optionVars, so they persist per user rather than per shot.

## Version

The version is `__version__` in `playblast_frames/__init__.py`, shown in the
window title, in the bottom-right corner of the window, and printed by the
installer. Bump it there when releasing, and
add an entry to [CHANGELOG.md](CHANGELOG.md).

```python
import playblast_frames
print(playblast_frames.__version__)
```
