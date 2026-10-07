"""Camera discovery and single-frame playblast capture."""

import contextlib
import os

import maya.cmds as cmds

from . import burnin


# (filename suffix, burn-in label, modelEditor settings, shader type or None)
# for each pass that can be written per camera. Passes run in this order, and
# a shader stays on the character once assigned, so the material pass, which
# needs the character's own shaders, must come first.
PASSES = (
    # The character's own shaders and textures.
    (
        "material",
        "Material",
        {
            "wireframeOnShaded": False,
            "useDefaultMaterial": False,
            "displayTextures": True,
        },
        None,
    ),
    # Neutral grey lambert so the wireframe reads cleanly over it.
    (
        "wireOnShaded",
        "Wireframe on Shaded",
        {
            "wireframeOnShaded": True,
            "useDefaultMaterial": False,
            "displayTextures": False,
        },
        "lambert",
    ),
    # A useBackground shader on the character draws its surface as the plate
    # behind it, but it still hides back-facing wires.
    (
        "wire",
        "Wireframe",
        {
            "wireframeOnShaded": True,
            "useDefaultMaterial": False,
            "displayTextures": False,
        },
        "useBackground",
    ),
)


def scene_cameras():
    """Return long transform paths of every non-startup camera, sorted by name."""
    cameras = []
    for shape in cmds.ls(type="camera", long=True) or []:
        if cmds.camera(shape, query=True, startupCamera=True):
            continue
        parents = cmds.listRelatives(shape, parent=True, fullPath=True)
        if parents:
            cameras.append(parents[0])
    return sorted(set(cameras), key=lambda path: short_name(path).lower())


def short_name(camera):
    """Leaf name of a long DAG path."""
    return camera.rsplit("|", 1)[-1]


def character_shapes(nodes):
    """Long paths of the mesh and NURBS surfaces at or under nodes."""
    shapes = cmds.ls(nodes, type=("mesh", "nurbsSurface"), long=True) or []
    shapes += (
        cmds.listRelatives(
            nodes, allDescendents=True, type=("mesh", "nurbsSurface"), fullPath=True
        )
        or []
    )
    return cmds.ls(shapes, noIntermediate=True, long=True) or []


def image_planes(camera):
    """Image plane shapes attached to the camera."""
    planes = []
    shapes = cmds.listRelatives(camera, shapes=True, type="camera", fullPath=True)
    for shape in shapes or []:
        planes += (
            cmds.listConnections(
                shape + ".imagePlane", source=True, destination=False, shapes=True
            )
            or []
        )
    return planes


CAPTURE_WIDTH = 3840


def capture_resolution():
    """4K-wide capture size, keeping the render globals' aspect ratio.

    Width is pinned rather than read from the render globals so every shot
    comes out at 4K, but the height still follows Render Settings so the
    framing matches what the shot actually renders.
    """
    width = cmds.getAttr("defaultResolution.width")
    height = cmds.getAttr("defaultResolution.height")
    return (CAPTURE_WIDTH, int(round(CAPTURE_WIDTH * height / float(width))))


def rig_name(camera):
    """Namespace the camera lives in, or the scene name when it has none."""
    leaf = short_name(camera)
    if ":" in leaf:
        return leaf.rsplit(":", 1)[0]
    scene = cmds.file(query=True, sceneName=True, shortName=True)
    return os.path.splitext(scene)[0] if scene else "untitled"


def camera_label(camera):
    """Camera name with its namespace stripped - the rig name already carries it."""
    return short_name(camera).rsplit(":", 1)[-1]


def _file_stem(camera, prefix=""):
    """Camera name with namespace separators made filename-safe, behind any prefix."""
    stem = short_name(camera).replace(":", "_")
    return prefix + "_" + stem if prefix else stem


# Viewport 2.0 anti-aliasing. lineAAEnable is the one that smooths wireframe
# lines; multisampling alone leaves them stair-stepped.
ANTI_ALIASING = {
    "lineAAEnable": True,
    "multiSampleEnable": True,
    "multiSampleCount": 16,
}


@contextlib.contextmanager
def _anti_aliasing():
    """Force Viewport 2.0 anti-aliasing on, restoring the scene's settings after."""
    previous = {}
    try:
        for attribute, value in ANTI_ALIASING.items():
            plug = "hardwareRenderingGlobals." + attribute
            previous[plug] = cmds.getAttr(plug)
            cmds.setAttr(plug, value)
        yield
    finally:
        for plug, value in previous.items():
            cmds.setAttr(plug, value)


@contextlib.contextmanager
def _undone_after(shapes, color):
    """Undo every scene edit made inside the block when it exits.

    Also gives the character's surfaces the one wireframe colour the user
    picked, unless color is None. The colour and _assign_shader both write
    to the scene, but they are undoable, so one undo restores exactly what
    each object had before - its shading assignments, including per-face ones,
    and any wireframe colour override it already carried.
    """
    undo_was_on = cmds.undoInfo(query=True, state=True)
    if not undo_was_on:
        cmds.undoInfo(state=True)
    cmds.undoInfo(openChunk=True)
    try:
        if color is not None:
            cmds.color(shapes, rgbColor=color)
        yield
    finally:
        cmds.undoInfo(closeChunk=True)
        cmds.undo()
        if not undo_was_on:
            cmds.undoInfo(state=False)


# A 4K window does not fit on a normal monitor, and playblast renders off
# screen at the size it is asked for regardless of how big the panel is. Only
# the aspect ratio has to match, so the framing on screen is the framing
# written to disk.
PANEL_MAX_WIDTH = 1280


def _panel_size(width, height):
    if width <= PANEL_MAX_WIDTH:
        return (width, height)
    return (PANEL_MAX_WIDTH, int(round(PANEL_MAX_WIDTH * height / float(width))))


@contextlib.contextmanager
def _capture_panel(width, height):
    """Temporary model panel in its own window, so the user's viewport is untouched."""
    window = cmds.window(
        title="Playblast Frames capture", widthHeight=_panel_size(width, height)
    )
    try:
        cmds.paneLayout()
        panel = cmds.modelPanel(menuBarVisible=False)
        # Hide everything, then re-enable only what belongs in the frame. This
        # drops locators, joints, curves, lights and the like in one flag.
        cmds.modelEditor(panel, edit=True, allObjects=False)
        cmds.modelEditor(
            panel,
            edit=True,
            # The anti-aliasing settings above are Viewport 2.0 only, so pin
            # the panel to it rather than inheriting whatever is current.
            rendererName="vp2Renderer",
            polymeshes=True,
            nurbsSurfaces=True,
            subdivSurfaces=True,
            imagePlane=True,
            displayAppearance="smoothShaded",
            displayLights="default",
            shadows=False,
            grid=False,
            headsUpDisplay=False,
            manipulators=False,
            selectionHiliteDisplay=False,
        )
        cmds.showWindow(window)
        yield panel
    finally:
        cmds.deleteUI(window, window=True)


def _assign_shader(shapes, shader_type):
    """Assign a new shader of shader_type to shapes. Call inside _undone_after."""
    shader = cmds.shadingNode(shader_type, asShader=True)
    group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True)
    cmds.connectAttr(shader + ".outColor", group + ".surfaceShader")
    cmds.sets(shapes, edit=True, forceElement=group)


def _isolate(panel, nodes):
    """Show only nodes (and what sits under them) in the panel."""
    cmds.select(nodes, replace=True)
    cmds.isolateSelect(panel, state=True)
    cmds.isolateSelect(panel, loadSelected=True)


def capture_batch(
    shots,
    character,
    output_dir,
    prefix="",
    wireframe_color=None,
    passes=None,
    on_progress=None,
):
    """Write the given passes for every camera, each at its own frame.

    shots is a list of (camera, frame) pairs. character is the list of nodes
    whose surfaces make up the character; only they and the camera's image
    planes are drawn.

    prefix, if given, is put in front of every filename, so a prefix of
    both_models and a camera called face_cam gives both_models_face_cam.

    wireframe_color is an (r, g, b) 0-1 tuple applied to the character for the
    duration of the batch, or None to leave its own wireframe colours alone.
    passes is a collection of PASSES suffixes to write, or None for all of
    them; they always run in PASSES order. Returns the list of image paths
    written. on_progress, if given, is called with each path as it is
    finished.
    """
    shapes = character_shapes(character)
    if not shapes:
        raise ValueError("No mesh or NURBS surfaces in the character geometry.")

    os.makedirs(output_dir, exist_ok=True)

    width, height = capture_resolution()
    written = []
    selection = cmds.ls(selection=True, long=True)

    try:
        with _anti_aliasing(), _undone_after(
            shapes, wireframe_color
        ), _capture_panel(width, height) as panel:
            for suffix, label, settings, shader_type in PASSES:
                if passes is not None and suffix not in passes:
                    continue
                if shader_type:
                    _assign_shader(shapes, shader_type)
                cmds.modelEditor(panel, edit=True, **settings)
                for camera, frame in shots:
                    cmds.modelEditor(panel, edit=True, camera=camera)
                    _isolate(panel, character + image_planes(camera))
                    # playblast grabs the focused panel.
                    cmds.setFocus(panel)
                    path = os.path.join(
                        output_dir, "%s_%s.png" % (_file_stem(camera, prefix), suffix)
                    )
                    cmds.playblast(
                        format="image",
                        compression="png",
                        completeFilename=path,
                        frame=[frame],
                        widthHeight=(width, height),
                        percent=100,
                        quality=100,
                        forceOverwrite=True,
                        showOrnaments=False,
                        offScreen=True,
                        clearCache=True,
                        viewer=False,
                    )
                    burnin.burn(
                        path,
                        "%s  |  %s  |  %s"
                        % (rig_name(camera), camera_label(camera), label),
                    )
                    written.append(path)
                    if on_progress:
                        on_progress(path)
    finally:
        # _isolate works through the selection, so put the user's back.
        if selection:
            cmds.select(selection, replace=True)
        else:
            cmds.select(clear=True)

    return written
