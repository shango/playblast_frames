# Playblast Frames 2.0.3

Grab quick 4K viewport stills of your character from lots of shot cameras at
once, each camera on its own frame. Needs Maya 2025 or newer.

## Install

1. Unzip `playblast_frames_2.0.3.zip`.
2. Drag `install.py` into a Maya viewport.

That's it. You get a **PBFrames** button on your current shelf, and the tool
opens.

## Quickstart

1. Pick cameras on the left and hit **Add**. The search box helps if you have a
   lot of them (type `080` to find `cam080`).
2. Set a frame for each camera in the **Frame** column. Or scrub the timeline,
   select some cameras and hit **Set to current frame**.
3. Select your character's geometry in Maya and hit **Set from selection**.
4. Tick the passes you want: **Wireframe**, **Shaded**, **Material**.
5. Pick an output folder and hit **Process**.

## What you get

One image per camera per pass, showing just the character over the image
plate:

- `cam080_wire.png` is the wireframe over the plate, with no back-facing wires.
- `cam080_wireOnShaded.png` is the wireframe on a grey lambert.
- `cam080_material.png` is the character with its own materials.

Each image has the rig, camera and pass written along the bottom.

## Good to know

- Your cameras, frames and character are saved in a small file next to your
  scene, so they come back when you reopen the shot.
- The tool doesn't change your scene. Anything it tweaks for the capture gets
  put back afterwards.
- The wireframe colour swatch sets one colour for all the wires. Untick it to
  keep the scene's own colours.
- The filename prefix is optional. `hero` turns `cam080_wire.png` into
  `hero_cam080_wire.png`.
