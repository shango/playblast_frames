# Changelog

Versions follow [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`.
The version lives in `playblast_frames/__init__.py` as `__version__` and is
shown in the window title.

## 2.0.2

- The queue's Frame column is wide enough for frame numbers like 1001; it
  was sized to the header text and cut four-digit frames off.

## 2.0.1

- Fixed **Add** (and double-click, Add all, Enter) doing nothing in 2.0.0: the
  queue table was handed a list item, so each add left a blank row with no
  camera or frame and raised an error in the Script Editor.

## 2.0.0

- Each queued camera has its own frame. The queue is a Camera | Frame table;
  cameras are added at the current frame, and **Set to current frame** stamps
  the time slider's frame onto the selected rows.
- Captures show only the character geometry, picked with **Set from
  selection**, plus the camera's image plane.
- Passes are now Wireframe (`wire`), Shaded (`wireOnShaded`) and Material
  (`material`), chosen with checkboxes; at least one stays on. The Wireframe
  pass puts a useBackground shader on the character so back-facing wires are
  hidden and the plate shows through. The old scene-wide `shaded` pass is
  replaced by the character-only Material pass.
- The wireframe colour applies to the character only.
- The queue file is now an object holding the character and each camera's
  frame. 1.x list files still load, at the current frame.
- Removed **Capture all cameras in scene**, since every camera needs a frame.
- The version is shown in the bottom-right corner of the window as well as the
  title bar.

## 1.1.0

- Burn-in on every image: rig name, camera and pass, along the bottom left.
  The rig name is the camera's namespace, falling back to the scene filename.
  Drawn with Qt, so there is nothing extra to install.
- Captures are 4K. Width is pinned to 3840 and the height follows the render
  globals' aspect ratio, so framing still matches the shot.
- The camera queue is saved to a JSON file beside the scene instead of a Maya
  optionVar, so the chosen cameras travel with the shot and survive a prefs
  reset. Loading no longer writes back, so opening the tool before a reference
  has loaded cannot wipe the saved queue.
- Wireframe colour is a single user-picked colour. The per-object contrasting
  colour option has been removed.
- Documented that anti-aliasing was already at Viewport 2.0's maximum
  (`multiSampleCount` 16 plus `lineAAEnable`). No behaviour change.

## 1.0.0

First release. Queue cameras with fuzzy search, capture a shaded and a
wire-on-shaded pass per camera at the current frame, at the render globals'
resolution.
