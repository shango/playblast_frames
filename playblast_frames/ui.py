"""PySide6 window for queueing cameras and capturing their playblast frames."""

import json
import os
import traceback

from PySide6 import QtCore, QtGui, QtWidgets
from shiboken6 import wrapInstance

import maya.cmds as cmds
import maya.OpenMayaUI as omui

from . import __version__, capture


OUTPUT_OPTION_VAR = "playblastFramesOutputDir"
WIRE_COLOR_OPTION_VAR = "playblastFramesWireColor"
WIRE_COLOR_ON_OPTION_VAR = "playblastFramesWireColorOn"
PREFIX_OPTION_VAR = "playblastFramesPrefix"
PASSES_OPTION_VAR = "playblastFramesPasses"

# Checkbox label for each capture.PASSES suffix, in the order they are shown.
PASS_LABELS = (
    ("wire", "Wireframe"),
    ("wireOnShaded", "Shaded"),
    ("material", "Material"),
)

DEFAULT_WIRE_COLOR = "#00ff00"

# The queue lives in a JSON file rather than an optionVar so the chosen
# cameras, their frames and the character survive a prefs reset and travel
# with the shot.
QUEUE_FILE_SUFFIX = "_playblast_cams.json"
UNTITLED_QUEUE_FILE = "playblast_frames_untitled_cams.json"


def maya_main_window():
    return wrapInstance(int(omui.MQtUtil.mainWindow()), QtWidgets.QWidget)


def fuzzy_match(pattern, text):
    """Score text against pattern, or return None when it does not match.

    Lower scores sort first. A substring hit always beats a subsequence hit,
    so typing "080" puts camera080 above camera0_8_0.
    """
    if not pattern:
        return (0, 0)

    pattern = pattern.lower()
    text = text.lower()

    index = text.find(pattern)
    if index != -1:
        return (0, index)

    # Subsequence: every character of the pattern appears in order.
    position = 0
    start = None
    for character in pattern:
        position = text.find(character, position)
        if position == -1:
            return None
        if start is None:
            start = position
        position += 1
    return (1, position - start)


def queue_file_path():
    """Where this scene's camera queue is stored.

    Beside the scene file, so the queue is per shot and comes back with it. An
    unsaved scene has nowhere to sit next to, so it falls back to the prefs
    folder.
    """
    scene = cmds.file(query=True, sceneName=True)
    if scene:
        return os.path.splitext(scene)[0] + QUEUE_FILE_SUFFIX
    return os.path.join(cmds.internalVar(userPrefDir=True), UNTITLED_QUEUE_FILE)


def read_queue_file():
    """(character nodes, [(camera, frame)]) saved for this scene.

    Files from 1.x are a plain list of cameras with no frames; those come back
    with a frame of None.
    """
    path = queue_file_path()
    if not os.path.isfile(path):
        return [], []
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        print("Playblast Frames: could not read %s (%s)" % (path, error))
        return [], []
    if isinstance(data, list):
        return [], [(str(camera), None) for camera in data]
    return (
        [str(node) for node in data.get("character", [])],
        [(str(shot["camera"]), int(shot["frame"])) for shot in data.get("cameras", [])],
    )


def write_queue_file(character, shots):
    """Save the character and the camera queue for this scene."""
    path = queue_file_path()
    data = {
        "character": character,
        "cameras": [{"camera": camera, "frame": frame} for camera, frame in shots],
    }
    try:
        with open(path, "w") as handle:
            json.dump(data, handle, indent=2)
    except OSError as error:
        # A read-only shot folder should not break the window on every edit.
        print("Playblast Frames: could not write %s (%s)" % (path, error))


def _frame_spin_box():
    spin = QtWidgets.QSpinBox()
    spin.setRange(-1000000, 1000000)
    return spin


def _current_frame():
    return int(round(cmds.currentTime(query=True)))


class PlayblastFramesWindow(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Playblast Frames %s" % __version__)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setMinimumSize(660, 440)

        self._cameras = []
        # Long paths of the nodes picked as the character's geometry.
        self._character = []
        self._wire_color = QtGui.QColor(DEFAULT_WIRE_COLOR)
        # Set while refresh_cameras prunes the queue, so a scene that is
        # missing cameras cannot wipe the saved selection.
        self._suspend_save = False

        self._build_ui()
        self._connect_signals()
        self.refresh_cameras()
        self._restore()

    def _build_ui(self):
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Fuzzy search - type 080 to find camera080")
        self.search.setClearButtonEnabled(True)
        self.refresh_button = QtWidgets.QPushButton("Refresh")

        self.available = QtWidgets.QListWidget()
        self.available.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.add_button = QtWidgets.QPushButton("Add  >")
        self.add_all_button = QtWidgets.QPushButton("Add all  >>")
        self.remove_button = QtWidgets.QPushButton("<  Remove")
        self.clear_button = QtWidgets.QPushButton("Clear")

        self.queue = QtWidgets.QTableWidget(0, 2)
        self.queue.setHorizontalHeaderLabels(["Camera", "Frame"])
        self.queue.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.queue.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        # Frames are edited through their spin boxes, camera names not at all.
        self.queue.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.queue.verticalHeader().setVisible(False)
        self.queue.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.Stretch
        )
        # ResizeToContents only measures the header text, not the spin boxes,
        # so size the column to a spin box, which is wide enough for its range.
        self.queue.horizontalHeader().setSectionResizeMode(
            1, QtWidgets.QHeaderView.Fixed
        )
        self.queue.setColumnWidth(1, _frame_spin_box().sizeHint().width())
        self.current_frame_button = QtWidgets.QPushButton("Set to current frame")
        self.current_frame_button.setToolTip(
            "Set the selected cameras to the time slider's current frame"
        )

        self.character = QtWidgets.QLineEdit()
        self.character.setReadOnly(True)
        self.character.setPlaceholderText(
            "Select the character's geometry group, then Set from selection"
        )
        self.character_button = QtWidgets.QPushButton("Set from selection")

        self.pass_boxes = {}
        for suffix, label in PASS_LABELS:
            box = QtWidgets.QCheckBox(label)
            box.setChecked(True)
            self.pass_boxes[suffix] = box

        self.wire_color_on = QtWidgets.QCheckBox("Wireframe colour")
        self.wire_color_on.setChecked(True)
        self.wire_color_button = QtWidgets.QPushButton()
        self.wire_color_button.setFixedWidth(60)
        self.wire_color_button.setToolTip("Pick the character's wireframe colour")

        self.queue_file_label = QtWidgets.QLabel()
        self.queue_file_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        self.queue_file_label.setStyleSheet("color: #808080;")

        self.prefix = QtWidgets.QLineEdit()
        self.prefix.setPlaceholderText(
            "Optional - both_models gives both_models_face_cam_shaded.png"
        )
        self.prefix.setClearButtonEnabled(True)

        self.output_dir = QtWidgets.QLineEdit()
        self.output_dir.setPlaceholderText(
            "Type an output folder path - created if missing"
        )
        self.browse_button = QtWidgets.QPushButton("Browse...")

        self.summary = QtWidgets.QLabel()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setVisible(False)
        self.process_button = QtWidgets.QPushButton("Process")
        # Also in the window title, but that is easy to miss or cut off.
        self.version_label = QtWidgets.QLabel("Playblast Frames %s" % __version__)
        self.version_label.setAlignment(QtCore.Qt.AlignRight)
        self.version_label.setStyleSheet("color: #808080;")

        search_row = QtWidgets.QHBoxLayout()
        search_row.addWidget(self.search)
        search_row.addWidget(self.refresh_button)

        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.add_all_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch()

        lists = QtWidgets.QGridLayout()
        lists.addWidget(QtWidgets.QLabel("Scene cameras"), 0, 0)
        lists.addLayout(search_row, 1, 0)
        lists.addWidget(self.available, 2, 0)
        lists.addLayout(buttons, 2, 1)
        lists.addWidget(QtWidgets.QLabel("Queue"), 0, 2)
        lists.addWidget(self.queue, 2, 2)
        lists.addWidget(self.current_frame_button, 3, 2)
        lists.setColumnStretch(0, 1)
        lists.setColumnStretch(2, 1)

        character_row = QtWidgets.QHBoxLayout()
        character_row.addWidget(QtWidgets.QLabel("Character geometry"))
        character_row.addWidget(self.character)
        character_row.addWidget(self.character_button)

        prefix_row = QtWidgets.QHBoxLayout()
        prefix_row.addWidget(QtWidgets.QLabel("Filename prefix"))
        prefix_row.addWidget(self.prefix)

        output_row = QtWidgets.QHBoxLayout()
        output_row.addWidget(QtWidgets.QLabel("Output folder"))
        output_row.addWidget(self.output_dir)
        output_row.addWidget(self.browse_button)

        passes_row = QtWidgets.QHBoxLayout()
        passes_row.addWidget(QtWidgets.QLabel("Passes"))
        for box in self.pass_boxes.values():
            passes_row.addWidget(box)
        passes_row.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        wire_row = QtWidgets.QHBoxLayout()
        wire_row.addWidget(self.wire_color_on)
        wire_row.addWidget(self.wire_color_button)
        wire_row.addStretch()

        layout.addLayout(lists)
        layout.addWidget(self.queue_file_label)
        layout.addLayout(character_row)
        layout.addLayout(passes_row)
        layout.addLayout(wire_row)
        layout.addLayout(prefix_row)
        layout.addLayout(output_row)
        layout.addWidget(self.summary)
        layout.addWidget(self.progress)
        layout.addWidget(self.process_button)
        layout.addWidget(self.version_label)

    def _connect_signals(self):
        self.search.textChanged.connect(self._apply_filter)
        self.search.returnPressed.connect(self._add_all_shown)
        self.refresh_button.clicked.connect(self.refresh_cameras)
        self.available.itemDoubleClicked.connect(self._add_double_clicked)
        self.add_button.clicked.connect(self._add_selected)
        self.add_all_button.clicked.connect(self._add_all_shown)
        self.remove_button.clicked.connect(self._remove_selected)
        self.clear_button.clicked.connect(self._clear_queue)
        self.current_frame_button.clicked.connect(self._set_to_current_frame)
        self.character_button.clicked.connect(self._set_character_from_selection)
        for box in self.pass_boxes.values():
            box.toggled.connect(self._on_pass_toggled)
        self.prefix.textChanged.connect(self._save)
        self.output_dir.textChanged.connect(self._save)
        self.wire_color_on.toggled.connect(self.wire_color_button.setEnabled)
        self.wire_color_on.toggled.connect(self._save)
        self.wire_color_button.clicked.connect(self._pick_wire_color)
        self.browse_button.clicked.connect(self._browse)
        self.process_button.clicked.connect(self.process)

    def refresh_cameras(self):
        """Rescan the scene, dropping queued cameras that no longer exist."""
        self._suspend_save = True
        try:
            self._cameras = capture.scene_cameras()
            self._apply_filter()
            for row in reversed(range(self.queue.rowCount())):
                if not cmds.objExists(self._queue_camera(row)):
                    self.queue.removeRow(row)
        finally:
            self._suspend_save = False
        self._update_summary()

    @staticmethod
    def _path_at(widget, row):
        return widget.item(row).data(QtCore.Qt.UserRole)

    def _queue_camera(self, row):
        return self.queue.item(row, 0).data(QtCore.Qt.UserRole)

    def _shots(self):
        """(camera, frame) for every queued camera, top to bottom."""
        return [
            (self._queue_camera(row), self.queue.cellWidget(row, 1).value())
            for row in range(self.queue.rowCount())
        ]

    @staticmethod
    def _make_item(camera):
        item = QtWidgets.QListWidgetItem(capture.short_name(camera))
        item.setData(QtCore.Qt.UserRole, camera)
        return item

    def _apply_filter(self):
        pattern = self.search.text().strip()
        matches = []
        for camera in self._cameras:
            name = capture.short_name(camera)
            score = fuzzy_match(pattern, name)
            if score is not None:
                matches.append((score, name.lower(), camera))
        matches.sort()

        self.available.clear()
        for _, _, camera in matches:
            self.available.addItem(self._make_item(camera))

    def _add_double_clicked(self, item):
        self._add_cameras([item.data(QtCore.Qt.UserRole)])

    def _add_selected(self):
        self._add_cameras(
            [item.data(QtCore.Qt.UserRole) for item in self.available.selectedItems()]
        )

    def _add_all_shown(self):
        """Queue every camera the current search is showing."""
        self._add_cameras(
            [self._path_at(self.available, row) for row in range(self.available.count())]
        )

    def _add_cameras(self, cameras):
        """Queue cameras at the current frame."""
        frame = _current_frame()
        self._add_shots([(camera, frame) for camera in cameras])

    def _add_shots(self, shots):
        queued = {self._queue_camera(row) for row in range(self.queue.rowCount())}
        for camera, frame in shots:
            if camera in queued:
                continue
            queued.add(camera)
            row = self.queue.rowCount()
            self.queue.insertRow(row)
            item = QtWidgets.QTableWidgetItem(capture.short_name(camera))
            item.setData(QtCore.Qt.UserRole, camera)
            self.queue.setItem(row, 0, item)
            spin = _frame_spin_box()
            spin.setValue(frame)
            spin.valueChanged.connect(self._save)
            self.queue.setCellWidget(row, 1, spin)
        self._queue_changed()

    def _selected_rows(self):
        return sorted({index.row() for index in self.queue.selectedIndexes()})

    def _remove_selected(self):
        for row in reversed(self._selected_rows()):
            self.queue.removeRow(row)
        self._queue_changed()

    def _clear_queue(self):
        self.queue.setRowCount(0)
        self._queue_changed()

    def _set_to_current_frame(self):
        frame = _current_frame()
        for row in self._selected_rows():
            self.queue.cellWidget(row, 1).setValue(frame)

    def _selected_passes(self):
        return [suffix for suffix, box in self.pass_boxes.items() if box.isChecked()]

    def _on_pass_toggled(self, checked):
        # At least one pass must stay on, so turning off the last one is undone.
        if not checked and not self._selected_passes():
            self.sender().setChecked(True)
            return
        self._update_summary()
        self._save()

    def _queue_changed(self):
        self._update_summary()
        self._save()

    def _set_character_from_selection(self):
        selected = cmds.ls(selection=True, long=True, objectsOnly=True) or []
        if not capture.character_shapes(selected):
            QtWidgets.QMessageBox.warning(
                self,
                "Playblast Frames",
                "Select the character's geometry (a group or meshes) first.",
            )
            return
        self._set_character(selected)
        self._save()

    def _set_character(self, nodes):
        self._character = nodes
        self.character.setText(", ".join(capture.short_name(node) for node in nodes))
        self.character.setToolTip("\n".join(nodes))
        self._update_summary()

    def _update_summary(self, *args):
        count = self.queue.rowCount()
        width, height = capture.capture_resolution()
        text = "%d camera(s) -> %d images at %dx%d" % (
            count,
            count * len(self._selected_passes()),
            width,
            height,
        )
        if not self._character:
            text += "  -  no character geometry set"
        self.summary.setText(text)

    def _save(self, *args):
        """Persist the queue to its JSON file and the settings as optionVars."""
        if self._suspend_save:
            return
        write_queue_file(self._character, self._shots())
        cmds.optionVar(stringValue=(PREFIX_OPTION_VAR, self.prefix.text()))
        cmds.optionVar(stringValue=(OUTPUT_OPTION_VAR, self.output_dir.text()))
        cmds.optionVar(
            stringValue=(PASSES_OPTION_VAR, " ".join(self._selected_passes()))
        )
        cmds.optionVar(stringValue=(WIRE_COLOR_OPTION_VAR, self._wire_color.name()))
        cmds.optionVar(
            intValue=(WIRE_COLOR_ON_OPTION_VAR, int(self.wire_color_on.isChecked()))
        )

    def _restore(self):
        """Reload the last session, matching saved cameras by name to this scene.

        Nothing here writes back: opening the tool before a reference has
        loaded would otherwise save an empty queue over the saved one.
        """
        self._suspend_save = True
        try:
            self._restore_saved()
        finally:
            self._suspend_save = False

    def _restore_saved(self):
        self.queue_file_label.setText("Camera queue file: %s" % queue_file_path())

        saved_character, saved_shots = read_queue_file()

        by_name = {capture.short_name(camera): camera for camera in self._cameras}
        restored = []
        for saved, frame in saved_shots:
            # Fall back to the short name so a re-opened or re-referenced
            # scene still restores, even when the full DAG path shifted.
            camera = saved if saved in self._cameras else by_name.get(
                capture.short_name(saved)
            )
            if camera:
                restored.append((camera, _current_frame() if frame is None else frame))
        self._add_shots(restored)

        character = []
        for saved in saved_character:
            # Same short-name fallback as the cameras, but only when it is
            # unambiguous.
            matches = cmds.ls(saved, long=True) or cmds.ls(
                capture.short_name(saved), long=True
            )
            if len(matches) == 1:
                character.append(matches[0])
        self._set_character(character)

        if cmds.optionVar(exists=PREFIX_OPTION_VAR):
            self.prefix.setText(cmds.optionVar(query=PREFIX_OPTION_VAR))
        if cmds.optionVar(exists=OUTPUT_OPTION_VAR):
            self.output_dir.setText(cmds.optionVar(query=OUTPUT_OPTION_VAR))
        if cmds.optionVar(exists=PASSES_OPTION_VAR):
            saved_passes = cmds.optionVar(query=PASSES_OPTION_VAR).split()
            # An empty or stale value would leave nothing ticked; keep the
            # all-on default instead.
            if set(saved_passes) & set(self.pass_boxes):
                for suffix, box in self.pass_boxes.items():
                    box.setChecked(suffix in saved_passes)
        if cmds.optionVar(exists=WIRE_COLOR_OPTION_VAR):
            saved_color = QtGui.QColor(cmds.optionVar(query=WIRE_COLOR_OPTION_VAR))
            if saved_color.isValid():
                self._wire_color = saved_color
        if cmds.optionVar(exists=WIRE_COLOR_ON_OPTION_VAR):
            self.wire_color_on.setChecked(
                bool(cmds.optionVar(query=WIRE_COLOR_ON_OPTION_VAR))
            )
        self._update_wire_swatch()
        self.wire_color_button.setEnabled(self.wire_color_on.isChecked())

    def _update_wire_swatch(self):
        self.wire_color_button.setStyleSheet(
            "background-color: %s; border: 1px solid #202020;" % self._wire_color.name()
        )

    def _pick_wire_color(self):
        chosen = QtWidgets.QColorDialog.getColor(
            self._wire_color, self, "Wireframe colour"
        )
        if chosen.isValid():
            self._wire_color = chosen
            self._update_wire_swatch()
            self._save()

    def _wireframe_color(self):
        """The colour to hand to capture, or None to leave the scene alone."""
        if not self.wire_color_on.isChecked():
            return None
        return (
            self._wire_color.redF(),
            self._wire_color.greenF(),
            self._wire_color.blueF(),
        )

    def _browse(self):
        start = self.output_dir.text() or cmds.workspace(
            query=True, rootDirectory=True
        )
        chosen = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Playblast output folder", start
        )
        if chosen:
            self.output_dir.setText(chosen)

    def _on_capture_progress(self, path):
        self.progress.setValue(self.progress.value() + 1)
        self.progress.setFormat("%s  (%%p%%)" % os.path.basename(path))
        QtWidgets.QApplication.processEvents()

    def process(self):
        shots = [shot for shot in self._shots() if cmds.objExists(shot[0])]
        if not shots:
            QtWidgets.QMessageBox.warning(
                self, "Playblast Frames", "Queue at least one camera first."
            )
            return

        character = [node for node in self._character if cmds.objExists(node)]
        if not character:
            QtWidgets.QMessageBox.warning(
                self, "Playblast Frames", "Set the character geometry first."
            )
            return

        output_dir = self.output_dir.text().strip()
        if not output_dir:
            QtWidgets.QMessageBox.warning(
                self, "Playblast Frames", "Choose an output folder first."
            )
            return

        passes = self._selected_passes()
        self.progress.setRange(0, len(shots) * len(passes))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.process_button.setEnabled(False)
        try:
            written = capture.capture_batch(
                shots,
                character,
                output_dir,
                prefix=self.prefix.text().strip(),
                wireframe_color=self._wireframe_color(),
                passes=passes,
                on_progress=self._on_capture_progress,
            )
        except Exception:
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "Playblast Frames",
                "Capture failed - see the Script Editor for details.",
            )
            return
        finally:
            self.process_button.setEnabled(True)
            self.progress.setVisible(False)

        QtWidgets.QMessageBox.information(
            self,
            "Playblast Frames",
            "Wrote %d images to:\n%s" % (len(written), output_dir),
        )


_window = None


def show():
    """Open the tool, replacing any window left over from a previous run."""
    global _window
    if _window is not None:
        try:
            _window.close()
            _window.deleteLater()
        except RuntimeError:
            pass
    _window = PlayblastFramesWindow(parent=maya_main_window())
    _window.show()
    return _window
