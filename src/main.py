import sys
import json
import os
import logging
import subprocess
import threading
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pyperclip
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QComboBox, QCheckBox,
    QLabel, QFileDialog, QMessageBox, QDialog, QSpinBox,
    QFrame, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor
from PyQt6.QtCore import QSize


class WorkerThread(QThread):
    """Background thread for long-running operations"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, target, args=()):
        super().__init__()
        self.target = target
        self.args = args
    
    def run(self):
        try:
            self.target(*self.args)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class YouTubePlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = self.load_config()
        self.mpv_path = self.config.get('mpv_path')
        self.log_dir = self.config.get('log_dir')
        self.max_history = int(self.config.get('max_history', '10'))
        self.ytdlp_path = self.config.get('ytdlp_path')
        self.is_playing = False
        
        self.process = None
        self.history = self.load_history()
        self.setup_logging()
        
        self.setWindowTitle("YouTube Player")
        self.setGeometry(100, 100, 700, 380)
        self.setMinimumSize(600, 320)
        
        self.setup_ui()
        self.setup_stylesheet()
        self.setup_timers()
        self.setup_shortcuts()
        
        self.logger.info("Application initialized successfully")
        
        # Update yt-dlp in background
        self.update_ytdlp_background()
    
    def load_config(self):
        """Load configuration from file or create default"""
        import configparser
        config = configparser.ConfigParser()
        # Get the src directory (where this script is located)
        src_dir = os.path.dirname(os.path.abspath(__file__))
        # Get the project root (one level up from src)
        project_root = os.path.dirname(src_dir)
        
        config_path = os.path.join(src_dir, 'config.ini')
        
        default_config = {
            'mpv_path': os.path.join(project_root, 'tools', 'mpv.exe'),
            'ytdlp_path': os.path.join(project_root, 'tools', 'yt-dlp.exe'),
            'log_dir': os.path.join(project_root, 'logs'),
            'max_history': '10'
        }
        
        if os.path.exists(config_path):
            config.read(config_path)
            if 'DEFAULT' not in config:
                config['DEFAULT'] = default_config
            else:
                # Merge defaults for any missing keys
                for key, value in default_config.items():
                    if key not in config['DEFAULT']:
                        config['DEFAULT'][key] = value
        else:
            config['DEFAULT'] = default_config
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                config.write(f)
        
        return dict(config['DEFAULT'])
    
    def save_config(self):
        """Save configuration to file"""
        import configparser
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'config.ini')
        
        if os.path.exists(config_path):
            config.read(config_path)
        
        if 'DEFAULT' not in config:
            config['DEFAULT'] = {}
        
        config['DEFAULT']['mpv_path'] = self.mpv_path
        config['DEFAULT']['ytdlp_path'] = self.ytdlp_path
        config['DEFAULT']['log_dir'] = self.log_dir
        config['DEFAULT']['max_history'] = str(self.max_history)
        
        with open(config_path, 'w') as f:
            config.write(f)
    
    def load_history(self):
        """Load URL history from file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        history_path = os.path.join(current_dir, 'history.json')
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_history(self):
        """Save URL history to file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        history_path = os.path.join(current_dir, 'history.json')
        
        if len(self.history) > self.max_history:
            keys_to_remove = sorted(self.history.keys(), 
                                    key=lambda x: self.history[x]['timestamp'])[:len(self.history) - self.max_history]
            for key in keys_to_remove:
                del self.history[key]
        
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def setup_logging(self):
        """Setup logging configuration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        log_file = os.path.join(self.log_dir, f'youtube_player_{timestamp}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(levelname)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_ui(self):
        """Setup the main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Header
        header = QLabel("YouTube Player")
        header_font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        header.setFont(header_font)
        header.setObjectName("header")
        main_layout.addWidget(header)
        
        # URL Input Section
        url_layout = QVBoxLayout()
        url_layout.setSpacing(8)
        
        url_label = QLabel("Video URL")
        url_label_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        url_label.setFont(url_label_font)
        url_layout.addWidget(url_label)
        
        input_layout = QHBoxLayout()
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste or enter YouTube URL...")
        self.url_input.setMinimumHeight(40)
        input_layout.addWidget(self.url_input)
        
        paste_btn = QPushButton("📋 Paste")
        paste_btn.setMinimumWidth(100)
        paste_btn.setMinimumHeight(40)
        paste_btn.clicked.connect(self.paste_url)
        paste_btn.setObjectName("actionButton")
        input_layout.addWidget(paste_btn)
        
        url_layout.addLayout(input_layout)
        
        # History Dropdown
        self.history_combo = QComboBox()
        self.history_combo.setMinimumHeight(35)
        self.history_combo.addItems(list(self.history.keys()))
        self.history_combo.currentIndexChanged.connect(self.select_history_url)
        self.history_combo.insertItem(0, "Recently played videos...")
        url_layout.addWidget(self.history_combo)
        
        main_layout.addLayout(url_layout)
        
        # Options Frame
        options_frame = QFrame()
        options_frame.setObjectName("optionsFrame")
        options_layout = QHBoxLayout(options_frame)
        options_layout.setContentsMargins(15, 12, 15, 12)
        options_layout.setSpacing(20)
        
        self.fullscreen_check = QCheckBox("🖥 Fullscreen")
        self.fullscreen_check.setChecked(True)
        self.fullscreen_check.setFont(QFont("Segoe UI", 10))
        options_layout.addWidget(self.fullscreen_check)
        
        self.loop_check = QCheckBox("🔄 Loop Video")
        self.loop_check.setFont(QFont("Segoe UI", 10))
        options_layout.addWidget(self.loop_check)
        
        options_layout.addStretch()
        main_layout.addWidget(options_frame)
        
        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setMinimumHeight(45)
        self.play_btn.setMinimumWidth(140)
        self.play_btn.clicked.connect(self.play_video)
        self.play_btn.setObjectName("primaryButton")
        button_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setMinimumHeight(45)
        self.stop_btn.setMinimumWidth(140)
        self.stop_btn.clicked.connect(self.stop_video)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setObjectName("dangerButton")
        button_layout.addWidget(self.stop_btn)
        
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setMinimumHeight(45)
        settings_btn.setMinimumWidth(140)
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setObjectName("actionButton")
        button_layout.addWidget(settings_btn)
        
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        # Add stretch to push everything to the top
        main_layout.addStretch()
        
        # Status Bar
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setObjectName("statusBar")
        main_layout.addWidget(self.status_label)
    
    def setup_stylesheet(self):
        """Setup modern stylesheet"""
        stylesheet = """
        QMainWindow {
            background-color: #f5f5f5;
        }
        
        #header {
            color: #1a1a1a;
        }
        
        QLineEdit {
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            padding: 8px 12px;
            background-color: white;
            font-family: 'Segoe UI';
            font-size: 10pt;
        }
        
        QLineEdit:focus {
            border: 2px solid #2196F3;
            background-color: white;
        }
        
        QPushButton {
            border: none;
            border-radius: 6px;
            font-family: 'Segoe UI';
            font-size: 10pt;
            font-weight: bold;
            padding: 8px 16px;
            transition: all 0.3s;
        }
        
        #primaryButton {
            background-color: #2196F3;
            color: white;
        }
        
        #primaryButton:hover {
            background-color: #1976D2;
        }
        
        #primaryButton:pressed {
            background-color: #1565C0;
        }
        
        #primaryButton:disabled {
            background-color: #ccc;
            color: #999;
        }
        
        #dangerButton {
            background-color: #f44336;
            color: white;
        }
        
        #dangerButton:hover {
            background-color: #da190b;
        }
        
        #dangerButton:pressed {
            background-color: #c41c00;
        }
        
        #dangerButton:disabled {
            background-color: #ccc;
            color: #999;
        }
        
        #actionButton {
            background-color: #757575;
            color: white;
        }
        
        #actionButton:hover {
            background-color: #616161;
        }
        
        #actionButton:pressed {
            background-color: #424242;
        }
        
        QComboBox {
            border: 2px solid #e0e0e0;
            border-radius: 6px;
            padding: 6px 12px;
            background-color: white;
            font-family: 'Segoe UI';
            font-size: 10pt;
        }
        
        QComboBox:focus {
            border: 2px solid #2196F3;
        }
        
        QCheckBox {
            color: #333;
            font-family: 'Segoe UI';
            font-size: 10pt;
            spacing: 6px;
        }
        
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 3px;
            border: 2px solid #999;
        }
        
        QCheckBox::indicator:checked {
            background-color: #2196F3;
            border: 2px solid #2196F3;
        }
        
        #optionsFrame {
            background-color: white;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }
        
        #logText {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 10px;
            color: #333;
        }
        
        #statusBar {
            color: #666;
            padding: 8px;
            background-color: #f0f0f0;
            border-radius: 4px;
        }
        
        QLabel {
            color: #333;
        }
        """
        self.setStyleSheet(stylesheet)
    
    def setup_timers(self):
        """Setup application timers"""
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_video_status)
        self.check_timer.start(1000)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        from PyQt6.QtGui import QKeySequence
        
        self.play_btn.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_P))
        self.stop_btn.setShortcut(QKeySequence(Qt.Key.Key_Escape))
    
    def validate_url(self, url):
        """Validate YouTube URL format"""
        patterns = [
            r'^(https?://)?(www\.)?(youtube\.com/watch\?v=[\w-]+(&\S*)?)',
            r'^(https?://)?(www\.)?(youtu\.be/[\w-]+(\?\S*)?)',
            r'^(https?://)?(www\.)?(youtube\.com/shorts/[\w-]+(\?\S*)?)',
            r'^(https?://)?(www\.)?(youtube\.com/playlist\?list=[\w-]+(&\S*)?)',
            r'^(https?://)?(www\.)?(youtube\.com/live/[\w-]+(\?\S*)?)'
        ]
        return any(re.match(pattern, url) for pattern in patterns)
    
    def paste_url(self):
        """Paste URL from clipboard"""
        try:
            clipboard_text = pyperclip.paste()
            self.url_input.setText(clipboard_text)
            self.logger.info("URL pasted from clipboard")
        except Exception as e:
            self.logger.error(f"Error pasting URL: {e}")
            QMessageBox.critical(self, "Error", "Failed to paste from clipboard")
    
    def select_history_url(self):
        """Handle history selection"""
        selected = self.history_combo.currentText()
        if selected in self.history:
            self.url_input.setText(selected)
            self.logger.info("Selected URL from history")
    
    def add_to_history(self, url):
        """Add URL to history"""
        if url not in self.history:
            self.history[url] = {
                'timestamp': datetime.now().isoformat(),
                'play_count': 1
            }
        else:
            self.history[url]['play_count'] += 1
            self.history[url]['timestamp'] = datetime.now().isoformat()
        
        self.save_history()
        self.history_combo.clear()
        self.history_combo.addItem("Recently played videos...")
        self.history_combo.addItems(list(self.history.keys()))
    
    def play_video(self):
        """Play video using MPV"""
        url = self.url_input.text().strip()
        
        if not url:
            self.logger.warning("Attempted to play with empty URL")
            QMessageBox.warning(self, "Error", "Please enter a URL")
            return
        
        if not self.validate_url(url):
            self.logger.warning(f"Invalid YouTube URL format: {url}")
            QMessageBox.warning(self, "Error", "Invalid YouTube URL format")
            return
        
        try:
            self.stop_video()
            self.logger.info(f"Starting video playback: {url}")
            
            cmd = [self.mpv_path]
            
            if self.fullscreen_check.isChecked():
                cmd.append('--fullscreen')
            
            if self.loop_check.isChecked():
                cmd.append('--loop-file=inf')
            
            cmd.extend(['--really-quiet', url])
            
            self.process = subprocess.Popen(cmd)
            self.add_to_history(url)
            self.update_ui_state(is_playing=True)
            self.status_label.setText("▶ Playing video...")
            
        except Exception as e:
            self.logger.error(f"Playback error: {e}")
            QMessageBox.critical(self, "Playback Error", str(e))
    
    def stop_video(self):
        """Stop video playback"""
        if self.process:
            try:
                self.logger.info("Stopping video playback")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
            except Exception as e:
                self.logger.error(f"Error stopping video: {e}")
        
        self.update_ui_state(is_playing=False)
        self.status_label.setText("Ready")
    
    def check_video_status(self):
        """Check if video is still playing"""
        if self.process:
            if self.process.poll() is not None:
                self.logger.info("Video playback completed")
                self.process = None
                self.update_ui_state(is_playing=False)
                self.status_label.setText("✓ Playback completed")
    
    def update_ui_state(self, is_playing):
        """Update UI state based on playback"""
        self.play_btn.setEnabled(not is_playing)
        self.stop_btn.setEnabled(is_playing)
        self.url_input.setEnabled(not is_playing)
        self.history_combo.setEnabled(not is_playing)
    
    def open_settings(self):
        """Open settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setGeometry(200, 200, 550, 450)
        dialog.setStyleSheet(self.styleSheet())
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # MPV Path
        mpv_label = QLabel("MPV Player Path:")
        mpv_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(mpv_label)
        
        mpv_layout = QHBoxLayout()
        mpv_input = QLineEdit(self.mpv_path)
        mpv_layout.addWidget(mpv_input)
        browse_mpv = QPushButton("Browse")
        browse_mpv.setMinimumWidth(100)
        browse_mpv.setObjectName("actionButton")
        browse_mpv.clicked.connect(lambda: self.browse_file(mpv_input, "MPV Player"))
        mpv_layout.addWidget(browse_mpv)
        layout.addLayout(mpv_layout)
        
        # YT-DLP Path
        ytdlp_label = QLabel("YT-DLP Path:")
        ytdlp_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(ytdlp_label)
        
        ytdlp_layout = QHBoxLayout()
        ytdlp_input = QLineEdit(self.ytdlp_path)
        ytdlp_layout.addWidget(ytdlp_input)
        browse_ytdlp = QPushButton("Browse")
        browse_ytdlp.setMinimumWidth(100)
        browse_ytdlp.setObjectName("actionButton")
        browse_ytdlp.clicked.connect(lambda: self.browse_file(ytdlp_input, "YT-DLP"))
        ytdlp_layout.addWidget(browse_ytdlp)
        layout.addLayout(ytdlp_layout)
        
        # Log Directory
        log_label = QLabel("Log Directory:")
        log_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(log_label)
        
        log_layout = QHBoxLayout()
        log_input = QLineEdit(self.log_dir)
        log_layout.addWidget(log_input)
        browse_log = QPushButton("Browse")
        browse_log.setMinimumWidth(100)
        browse_log.setObjectName("actionButton")
        browse_log.clicked.connect(lambda: self.browse_directory(log_input))
        log_layout.addWidget(browse_log)
        layout.addLayout(log_layout)
        
        # Max History
        history_label = QLabel("Max History Items:")
        history_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(history_label)
        
        history_spin = QSpinBox()
        history_spin.setValue(self.max_history)
        history_spin.setMinimum(1)
        history_spin.setMaximum(100)
        layout.addWidget(history_spin)
        
        # Clear History Button
        clear_btn = QPushButton("Clear History")
        clear_btn.setObjectName("dangerButton")
        clear_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_btn)
        
        layout.addStretch()
        
        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.setMinimumHeight(40)
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(lambda: self.save_settings_dialog(
            mpv_input.text(),
            ytdlp_input.text(),
            log_input.text(),
            str(history_spin.value()),
            dialog
        ))
        layout.addWidget(save_btn)
        
        dialog.exec()
    
    def browse_file(self, input_widget, file_type="File"):
        """Browse for file"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, f"Select {file_type}", "", "Executable Files (*.exe);;All Files (*.*)"
        )
        if filepath:
            input_widget.setText(filepath)
    
    def browse_directory(self, input_widget):
        """Browse for directory"""
        directory = QFileDialog.getExistingDirectory(self, "Select Log Directory")
        if directory:
            input_widget.setText(directory)
    
    def save_settings_dialog(self, mpv_path, ytdlp_path, log_dir, max_history, dialog):
        """Save settings"""
        try:
            self.mpv_path = mpv_path
            self.ytdlp_path = ytdlp_path
            self.log_dir = log_dir
            self.max_history = int(max_history)
            self.save_config()
            self.logger.info("Settings saved successfully")
            dialog.close()
            QMessageBox.information(self, "Success", "Settings saved successfully!")
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
    
    def clear_history(self):
        """Clear URL history"""
        reply = QMessageBox.question(
            self, "Confirm", "Are you sure you want to clear all history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.history = {}
            self.save_history()
            self.history_combo.clear()
            self.history_combo.addItem("Recently played videos...")
            self.logger.info("History cleared")
    
    def update_ytdlp_background(self):
        """Update yt-dlp in background"""
        def update():
            try:
                if not os.path.exists(self.ytdlp_path):
                    self.logger.warning(f"yt-dlp not found at {self.ytdlp_path}")
                    return
                
                self.logger.info("Updating yt-dlp...")
                process = subprocess.Popen(
                    [self.ytdlp_path, "-U"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                process.communicate(timeout=30)
                self.logger.info("yt-dlp updated successfully")
            except Exception as e:
                self.logger.warning(f"Error updating yt-dlp: {e}")
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()
    
    def closeEvent(self, event):
        """Handle window close"""
        self.logger.info("Application shutting down")
        self.stop_video()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = YouTubePlayerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()