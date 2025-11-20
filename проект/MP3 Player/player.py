from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PyQt6 import QtCore, QtGui, QtWidgets, QtMultimedia


SUPPORTED_EXTENSIONS = {"mp3", "wav", "flac", "ogg", "m4a", "aac"}


@dataclass
class Track:
    """Simple track model.

    Attributes:
        path: absolute path to file
        title: display name
    """

    path: str
    title: str

    @staticmethod
    def from_path(path: Path) -> "Track":
        return Track(path=str(path), title=path.stem)


class Mp3Player(QtWidgets.QMainWindow):
    """Advanced MP3 player with drag & drop and mini-player."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MP3 Player — PyQt6")
        self.resize(820, 480)
        self.setAcceptDrops(True)

        self.tracks: List[Track] = []
        self.current_index: Optional[int] = None
        self._seeking = False

        # Use persistent storage in AppData for EXE
        self.data_dir = Path.home() / "AppData" / "Local" / "Mp3PlayerData"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.last_session_file = self.data_dir / "last_session.m3u"

        self._setup_player()
        self._setup_ui()
        self._connect_signals()

        # Auto-load last session
        # Load last volume and last track info
        last_volume = self.data_dir / "last_volume.txt"
        last_state = self.data_dir / "last_state.txt"
        if self.last_session_file.exists():
            try:
                with open(self.last_session_file, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                for p in lines:
                    file_path = Path(p)
                    if file_path.exists():
                        track = Track.from_path(file_path)
                        self.tracks.append(track)
                        self.playlist_widget.addItem(track.title)
            except Exception:
                pass

        # Load last volume
        if last_volume.exists():
            try:
                v = float(last_volume.read_text().strip())
                self.audio_output.setVolume(v)
                self.volume_slider.setValue(int(v * 100))
            except Exception:
                pass

        # Load last state (track index and position)
        if last_state.exists():
            try:
                data = last_state.read_text().split("|")
                if len(data) == 2:
                    idx, pos = int(data[0]), int(data[1])
                    if 0 <= idx < len(self.tracks):
                        self.current_index = idx
                        self.playlist_widget.setCurrentRow(idx)
                        self._play_index(idx)
                        self.player.setPosition(pos)
                        self.player.pause()
            except Exception:
                pass
                pass

    # -------------------- PLAYER --------------------

    def _setup_player(self) -> None:
        self.player = QtMultimedia.QMediaPlayer(self)
        self.audio_output = QtMultimedia.QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.8)

    # -------------------- UI --------------------

    def _setup_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        self.main_layout = QtWidgets.QVBoxLayout(central)

        # Top toolbar with file actions and mini-player toggle
        top_toolbar = QtWidgets.QHBoxLayout()
        self.btn_add = QtWidgets.QPushButton("Добавить")
        self.btn_remove = QtWidgets.QPushButton("Удалить")
        self.btn_save = QtWidgets.QPushButton("Сохранить")
        self.btn_load = QtWidgets.QPushButton("Загрузить")
        self.btn_toggle_mini = QtWidgets.QPushButton("Мини-плеер")
        top_toolbar.addWidget(self.btn_add)
        top_toolbar.addWidget(self.btn_remove)
        top_toolbar.addWidget(self.btn_save)
        top_toolbar.addWidget(self.btn_load)
        top_toolbar.addStretch()
        top_toolbar.addWidget(self.btn_toggle_mini)
        self.main_layout.addLayout(top_toolbar)

        # Middle: playlist and mini-player stacked
        self.stack = QtWidgets.QStackedWidget()

        # Full widget: playlist + controls
        self.full_widget = QtWidgets.QWidget()
        fw_layout = QtWidgets.QVBoxLayout(self.full_widget)

        # Playlist
        self.playlist_widget = QtWidgets.QListWidget()
        self.playlist_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        fw_layout.addWidget(self.playlist_widget)

        # Playback controls row
        controls = QtWidgets.QHBoxLayout()
        self.btn_play = QtWidgets.QPushButton("Play")
        self.btn_pause = QtWidgets.QPushButton("Pause")  # will toggle to ▶ automatically
        self.btn_stop = QtWidgets.QPushButton("Stop")
        controls.addWidget(self.btn_play)
        controls.addWidget(self.btn_pause)
        controls.addWidget(self.btn_stop)

        # Seek slider and time
        self.seek_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        controls.addWidget(self.seek_slider)
        self.time_label = QtWidgets.QLabel("00:00 / 00:00")
        controls.addWidget(self.time_label)

        # Volume
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        controls.addWidget(QtWidgets.QLabel("Vol"))
        controls.addWidget(self.volume_slider)

        fw_layout.addLayout(controls)

        # Mini-player: compact controls only
        self.mini_widget = QtWidgets.QWidget()
        mw_layout = QtWidgets.QHBoxLayout(self.mini_widget)
        self.mini_btn_prev = QtWidgets.QPushButton("⟸")
        self.mini_btn_play = QtWidgets.QPushButton("Play")
        self.mini_btn_next = QtWidgets.QPushButton("⟹")
        self.mini_label = QtWidgets.QLabel("No track")
        mw_layout.addWidget(self.mini_btn_prev)
        mw_layout.addWidget(self.mini_btn_play)
        mw_layout.addWidget(self.mini_btn_next)
        mw_layout.addWidget(self.mini_label)

        # Add both to stack
        self.stack.addWidget(self.full_widget)
        self.stack.addWidget(self.mini_widget)
        self.main_layout.addWidget(self.stack)

        # Status bar
        self.status = QtWidgets.QStatusBar()
        self.setStatusBar(self.status)

    # -------------------- SIGNALS --------------------

    def _connect_signals(self) -> None:
        self.btn_add.clicked.connect(self.add_tracks)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_save.clicked.connect(self.save_playlist)
        self.btn_load.clicked.connect(self.load_playlist)
        self.btn_toggle_mini.clicked.connect(self.toggle_mini_mode)

        self.btn_play.clicked.connect(self.play_selected)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_stop.clicked.connect(self.player.stop)

        self.mini_btn_play.clicked.connect(self.play_selected)
        self.mini_btn_prev.clicked.connect(self.play_prev)
        self.mini_btn_next.clicked.connect(self.play_next)

        self.playlist_widget.itemDoubleClicked.connect(self.on_item_double)

        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status)

        self.seek_slider.sliderPressed.connect(self.on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self.on_seek_released)
        self.seek_slider.sliderMoved.connect(self.on_seek_moved)

        self.volume_slider.valueChanged.connect(
            lambda v: self.audio_output.setVolume(v / 100)
        )

    # -------------------- DRAG & DROP --------------------

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # type: ignore
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # type: ignore
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        added = 0
        for p in paths:
            path_obj = Path(p)
            if path_obj.is_file() and path_obj.suffix.lower().lstrip('.') in SUPPORTED_EXTENSIONS:
                track = Track.from_path(path_obj)
                self.tracks.append(track)
                self.playlist_widget.addItem(track.title)
                added += 1
        self.status.showMessage(f"Добавлено перетаскиванием: {added}", 3000)

    # -------------------- ADD / REMOVE TRACKS --------------------

    def add_tracks(self) -> None:
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Добавить треки",
            str(Path.home()),
            "Audio (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;All files (*)",
        )

        added = 0
        for p in paths:
            path_obj = Path(p)
            ext = path_obj.suffix.lower().lstrip('.')
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            track = Track.from_path(path_obj)
            self.tracks.append(track)
            self.playlist_widget.addItem(track.title)
            added += 1

        self.status.showMessage(f"Добавлено: {added}", 3000)

    def remove_selected(self) -> None:
        sel = self.playlist_widget.currentRow()
        if sel < 0:
            return

        if self.current_index == sel:
            self.player.stop()
            self.current_index = None

        self.playlist_widget.takeItem(sel)
        try:
            del self.tracks[sel]
        except IndexError:
            pass

    # -------------------- PLAYBACK --------------------

    def toggle_pause(self) -> None:
        """Pause button toggles pause/resume and updates its label."""
        state = self.player.playbackState()
        if state == QtMultimedia.QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_pause.setText("▶")  # change to resume icon
        elif state == QtMultimedia.QMediaPlayer.PlaybackState.PausedState:
            self.player.play()
            self.btn_pause.setText("Pause")  # back to pause
        else:
            self.play_selected()
            self.btn_pause.setText("Pause")

    def play_selected(self) -> None:
        row = self.playlist_widget.currentRow()
        if row < 0 and self.tracks:
            row = 0
            self.playlist_widget.setCurrentRow(0)

        if row < 0:
            self.status.showMessage("Плейлист пуст", 2000)
            return

        # --- Resume from pause ---
        if (
            self.current_index == row
            and self.player.playbackState() == QtMultimedia.QMediaPlayer.PlaybackState.PausedState
        ):
            self.player.play()
            return

        self._play_index(row)

    def on_item_double(self, item: QtWidgets.QListWidgetItem) -> None:
        row = self.playlist_widget.row(item)
        self._play_index(row)

    def _play_index(self, index: int) -> None:
        try:
            track = self.tracks[index]
        except IndexError:
            return

        url = QtCore.QUrl.fromLocalFile(track.path)
        self.player.setSource(url)
        self.player.play()
        self.current_index = index
        self._update_mini_label()
        self.status.showMessage(f"Воспроизведение: {track.title}")

    def play_next(self) -> None:
        if self.current_index is None:
            return
        nxt = self.current_index + 1
        if nxt < len(self.tracks):
            self.playlist_widget.setCurrentRow(nxt)
            self._play_index(nxt)
        else:
            self.player.stop()
            self.current_index = None

    def play_prev(self) -> None:
        if self.current_index is None:
            return
        prev = max(0, self.current_index - 1)
        self.playlist_widget.setCurrentRow(prev)
        self._play_index(prev)

    # -------------------- SEEK & TIME --------------------

    def on_position_changed(self, position: int) -> None:
        if self._seeking:
            return
        duration = self.player.duration()
        if duration > 0:
            value = int(position / duration * self.seek_slider.maximum())
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(value)
            self.seek_slider.blockSignals(False)
        self.time_label.setText(f"{self._format_time(position)} / {self._format_time(duration)}")

    def on_duration_changed(self, duration: int) -> None:
        # update time label when duration becomes known
        self.time_label.setText(f"{self._format_time(self.player.position())} / {self._format_time(duration)}")

    def on_seek_pressed(self) -> None:
        self._seeking = True

    def on_seek_released(self) -> None:
        self._seeking = False
        self.on_seek_moved(self.seek_slider.value())

    def on_seek_moved(self, slider_value: int) -> None:
        duration = self.player.duration()
        if duration <= 0:
            return
        pos = int(slider_value / self.seek_slider.maximum() * duration)
        self.player.setPosition(pos)

    # -------------------- MEDIA STATUS --------------------

    def on_media_status(self, status: QtMultimedia.QMediaPlayer.MediaStatus) -> None:
        if status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_next()

    # -------------------- PLAYLIST SAVE / LOAD --------------------

    def save_playlist(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Сохранить плейлист", "playlist.m3u", "M3U Playlist (*.m3u)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for t in self.tracks:
                    f.write(t.path + "\n")
            self.status.showMessage(f"Плейлист сохранён: {path}", 3000)
        except Exception:
            self.status.showMessage("Ошибка сохранения плейлиста", 3000)

    def load_playlist(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Загрузить плейлист", "", "M3U Playlist (*.m3u)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            self.tracks.clear()
            self.playlist_widget.clear()
            for p in lines:
                file_path = Path(p)
                if file_path.exists():
                    track = Track.from_path(file_path)
                    self.tracks.append(track)
                    self.playlist_widget.addItem(track.title)
            self.status.showMessage("Плейлист загружен", 3000)
        except Exception:
            self.status.showMessage("Ошибка загрузки плейлиста", 3000)

    # -------------------- MINI-PLAYER --------------------

    def toggle_mini_mode(self) -> None:
        if self.stack.currentWidget() is self.full_widget:
            self.stack.setCurrentWidget(self.mini_widget)
            self.btn_toggle_mini.setText("Развернуть")
        else:
            self.stack.setCurrentWidget(self.full_widget)
            self.btn_toggle_mini.setText("Мини-плеер")

    def _update_mini_label(self) -> None:
        if self.current_index is None:
            self.mini_label.setText("No track")
        else:
            self.mini_label.setText(self.tracks[self.current_index].title)

    # -------------------- UTIL --------------------

    @staticmethod
    def _format_time(ms: int) -> str:
        if ms is None or ms <= 0:
            return "00:00"
        seconds = int(ms / 1000)
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Save session automatically on exit (tracks, volume, current track)."""
        try:
            # Сохраняем список треков
            with open(self.last_session_file, "w", encoding="utf-8") as f:
                for t in self.tracks:
                    f.write(t.path + "\n")
        except Exception:
            pass

        # Сохраняем громкость
        try:
            (self.data_dir / "last_volume.txt").write_text(str(self.audio_output.volume()))
        except Exception:
            pass

        # Сохраняем текущий трек и позицию
        try:
            idx = self.current_index if self.current_index is not None else -1
            pos = self.player.position()
            (self.data_dir / "last_state.txt").write_text(f"{idx}|{pos}")
        except Exception:
            pass

        event.accept()

# -------------------- MAIN --------------------


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = Mp3Player()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
