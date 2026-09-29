"""Drag this file into a Maya 2025+ viewport to install Playblast Frames.

Copies the playblast_frames package into the user scripts directory and adds a
button to the current shelf.
"""

import inspect
import os
import shutil
import sys

import maya.cmds as cmds
import maya.mel as mel


PACKAGE = "playblast_frames"
SHELF_LABEL = "PBFrames"
SHELF_COMMAND = "import playblast_frames\nplayblast_frames.show()"


def _installer_dir():
    """Directory holding this file - __file__ is not set for dropped scripts."""
    return os.path.dirname(os.path.abspath(inspect.getsourcefile(lambda: 0)))


def _add_shelf_button():
    shelf_top_level = mel.eval("$tmp = $gShelfTopLevel")
    shelf = cmds.tabLayout(shelf_top_level, query=True, selectTab=True)

    for control in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        if cmds.objectTypeUI(control) != "shelfButton":
            continue
        if cmds.shelfButton(control, query=True, label=True) == SHELF_LABEL:
            cmds.deleteUI(control)

    cmds.shelfButton(
        parent=shelf,
        label=SHELF_LABEL,
        annotation="Single-frame playblasts from multiple cameras",
        image="pythonFamily.png",
        imageOverlayLabel="PBF",
        sourceType="python",
        command=SHELF_COMMAND,
    )
    mel.eval("saveAllShelves $gShelfTopLevel")


def onMayaDroppedPythonFile(*args):
    source = os.path.join(_installer_dir(), PACKAGE)
    if not os.path.isdir(source):
        cmds.error("Could not find the '%s' folder next to install.py." % PACKAGE)

    scripts_dir = os.path.join(cmds.internalVar(userAppDir=True), "scripts")
    destination = os.path.join(scripts_dir, PACKAGE)

    if os.path.normpath(source) != os.path.normpath(destination):
        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    if scripts_dir not in sys.path:
        sys.path.append(scripts_dir)

    # Drop anything imported before this install so the new files are used.
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(PACKAGE + ".")]:
        del sys.modules[name]

    _add_shelf_button()

    import playblast_frames

    print(
        "Playblast Frames %s installed to: %s"
        % (playblast_frames.__version__, destination)
    )
    playblast_frames.show()
