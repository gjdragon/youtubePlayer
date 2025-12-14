import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import subprocess
import pyperclip
import logging
from datetime import datetime
import re
import sys
import os
import json
import configparser
from urllib.parse import urlparse, parse_qs
from pathlib import Path

class YouTubePlayerApp:
    def __init__(self):
        self.config = self.load_config()
        self.mpv_path = self.config.get('mpv_path')
        self.log_dir = self.config.get('log_dir')
        self.max_history = int(self.config.get('max_history', '10'))
        self.ytdlp_path = self.config.get('ytdlp_path')
        
        self.process = None
        self.history = self.load_history()
        self.setup_logging()
        
        # Update yt-dlp on startup
        self.update_ytdlp()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("YouTube Player v1.0.0")
        self.root.geometry("700x500")
        self.root.minsize(550, 400)
        
        # Set icon if available
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'youtube.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass
        
        # Configure style
        self.setup_theme()
        
        # Configure grid weights
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create main frame with padding
        self.main_frame = ttk.Frame(self.root, padding="12")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)
        
        # Title
        self.setup_title()
        
        # URL Input Frame
        self.setup_url_frame()
        
        # Button Frame
        self.setup_button_frame()
        
        # Playback Options Frame
        self.setup_options_frame()
        
        # Log Display
        self.setup_log_frame()
        
        # Status bar
        self.setup_status_bar()
        
        # Setup event handlers
        self.root.after(1000, self.check_video_status)
        self.setup_keyboard_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logger.info("Application initialized successfully")
    
    def load_config(self):
        """Load configuration from file or create default"""
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, 'config.ini')
        
        # Default settings with relative paths
        default_config = {
            'mpv_path': os.path.join(current_dir, 'tools', 'mpv.exe'),
            'ytdlp_path': os.path.join(current_dir, 'tools', 'yt-dlp.exe'),
            'log_dir': os.path.join(current_dir, 'logs'),
            'max_history': '10'
        }
        
        if os.path.exists(config_path):
            config.read(config_path)
            if 'DEFAULT' not in config:
                config['DEFAULT'] = {}
            for key, value in default_config.items():
                if key not in config['DEFAULT']:
                    config['DEFAULT'][key] = value
            with open(config_path, 'w') as f:
                config.write(f)
        else:
            config['DEFAULT'] = default_config
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                config.write(f)
        
        return config['DEFAULT']
    
    def save_config(self):
        """Save current configuration to file"""
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
    
    def setup_theme(self):
        """Setup modern theme for the application"""
        style = ttk.Style()
        available_themes = style.theme_names()
        
        if 'clam' in available_themes:
            style.theme_use('clam')
        elif 'vista' in available_themes:
            style.theme_use('vista')
        
        # Configure custom colors for better appearance
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('Accent.TButton', font=('Helvetica', 10))
    
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
        self.text_handler = None
    
    def update_ytdlp(self):
        """Update yt-dlp on startup in background thread"""
        def run_update():
            try:
                if not os.path.exists(self.ytdlp_path):
                    self.logger.warning(f"yt-dlp not found at {self.ytdlp_path}")
                    return
                
                self.logger.info("Updating yt-dlp...")
                update_process = subprocess.Popen(
                    [self.ytdlp_path, "-U"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                stdout, stderr = update_process.communicate(timeout=30)
                
                if update_process.returncode == 0:
                    self.logger.info("yt-dlp updated successfully")
                else:
                    self.logger.warning(f"yt-dlp update returned code {update_process.returncode}")
            except subprocess.TimeoutExpired:
                self.logger.warning("yt-dlp update timed out")
            except Exception as e:
                self.logger.warning(f"Error updating yt-dlp: {e}")
        
        # Run update in background thread to avoid blocking UI
        import threading
        update_thread = threading.Thread(target=run_update, daemon=True)
        update_thread.start()
    
    def setup_text_handler(self):
        """Setup text handler for log display"""
        class TextHandler(logging.Handler):
            def __init__(self, text_widget):
                logging.Handler.__init__(self)
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record) + '\n'
                self.text_widget.insert(tk.END, msg)
                self.text_widget.see(tk.END)
        
        self.text_handler = TextHandler(self.log_text)
        self.text_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
        self.text_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.text_handler)
    
    def setup_title(self):
        """Setup application title"""
        title_label = ttk.Label(self.main_frame, text="YouTube Player", style='Title.TLabel')
        title_label.grid(row=0, column=0, sticky="w", padx=5, pady=(0, 10))
    
    def setup_url_frame(self):
        """Setup URL input frame"""
        url_frame = ttk.LabelFrame(self.main_frame, text="Video URL", padding="8")
        url_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        url_frame.columnconfigure(0, weight=1)
        
        self.url_var = tk.StringVar()
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=3)
        
        self.url_history_combo = ttk.Combobox(
            url_frame, 
            values=list(self.history.keys()), 
            state="readonly",
            height=6
        )
        self.url_history_combo.grid(row=1, column=0, sticky="ew", padx=5, pady=3)
        self.url_history_combo.bind("<<ComboboxSelected>>", self.select_history_url)
    
    def setup_button_frame(self):
        """Setup control buttons frame"""
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=2, column=0, pady=12)
        
        self.paste_btn = ttk.Button(button_frame, text="📋 Paste", command=self.paste_url, width=12)
        self.paste_btn.pack(side=tk.LEFT, padx=4)
        
        self.play_btn = ttk.Button(button_frame, text="▶ Play", command=self.play_video, width=12)
        self.play_btn.pack(side=tk.LEFT, padx=4)
        
        self.stop_btn = ttk.Button(button_frame, text="⏹ Stop", command=self.stop_video, state=tk.DISABLED, width=12)
        self.stop_btn.pack(side=tk.LEFT, padx=4)
        
        self.settings_btn = ttk.Button(button_frame, text="⚙ Settings", command=self.open_settings, width=12)
        self.settings_btn.pack(side=tk.LEFT, padx=4)
    
    def setup_options_frame(self):
        """Setup playback options frame"""
        options_frame = ttk.LabelFrame(self.main_frame, text="Playback Options", padding="8")
        options_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=5)
        options_frame.columnconfigure(0, weight=1)
        
        self.fullscreen_var = tk.BooleanVar(value=True)
        self.fullscreen_check = ttk.Checkbutton(
            options_frame, 
            text="🖥 Fullscreen", 
            variable=self.fullscreen_var
        )
        self.fullscreen_check.grid(row=0, column=0, sticky="w", padx=5)
        
        self.loop_var = tk.BooleanVar(value=False)
        self.loop_check = ttk.Checkbutton(
            options_frame, 
            text="🔄 Loop Video", 
            variable=self.loop_var
        )
        self.loop_check.grid(row=0, column=1, sticky="w", padx=5)
    
    def setup_log_frame(self):
        """Setup log display frame"""
        log_frame = ttk.LabelFrame(self.main_frame, text="Activity Log", padding="8")
        log_frame.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD, relief="sunken", bd=1)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)
    
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(
            self.main_frame, 
            textvariable=self.status_var, 
            relief="sunken",
            anchor="w"
        )
        self.status_bar.grid(row=5, column=0, sticky="ew", pady=(5, 0))
    
    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts"""
        self.root.bind('<Control-v>', lambda e: self.paste_url())
        self.root.bind('<Control-p>', lambda e: self.play_video())
        self.root.bind('<Escape>', lambda e: self.stop_video())
    
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
    
    def get_video_title(self, url):
        """Extract video title from URL if available"""
        try:
            parsed_url = urlparse(url)
            if 'youtube.com' in parsed_url.netloc:
                query = parse_qs(parsed_url.query)
                if 'v' in query:
                    return f"Video ID: {query['v'][0]}"
            elif 'youtu.be' in parsed_url.netloc:
                return f"Video ID: {parsed_url.path.strip('/')}"
        except:
            pass
        return url
    
    def paste_url(self):
        """Paste clipboard content into URL entry"""
        try:
            clipboard_text = pyperclip.paste()
            self.url_var.set(clipboard_text)
            self.logger.info("URL pasted from clipboard")
        except Exception as e:
            self.logger.error(f"Error pasting URL: {e}")
            messagebox.showerror("Error", "Failed to paste from clipboard")
    
    def select_history_url(self, event=None):
        """Handle history URL selection"""
        selected = self.url_history_combo.get()
        if selected in self.history:
            self.url_var.set(selected)
            self.logger.info(f"Selected URL from history")
    
    def add_to_history(self, url):
        """Add URL to history"""
        if url not in self.history:
            self.history[url] = {
                'title': self.get_video_title(url),
                'timestamp': datetime.now().isoformat(),
                'play_count': 1
            }
        else:
            self.history[url]['play_count'] += 1
            self.history[url]['timestamp'] = datetime.now().isoformat()
        
        self.save_history()
        self.url_history_combo['values'] = list(self.history.keys())
    
    def play_video(self):
        """Play video using MPV"""
        url = self.url_var.get().strip()
        
        if not url:
            self.logger.warning("Attempted to play with empty URL")
            messagebox.showerror("Error", "Please enter a URL")
            return
        
        if not self.validate_url(url):
            self.logger.warning(f"Invalid YouTube URL format: {url}")
            messagebox.showerror("Error", "Invalid YouTube URL format")
            return
        
        try:
            self.stop_video()
            self.logger.info(f"Starting video playback: {url}")
            
            cmd = [self.mpv_path]
            
            if self.fullscreen_var.get():
                cmd.append('--fullscreen')
            
            if self.loop_var.get():
                cmd.append('--loop-file=inf')
            
            cmd.extend(['--really-quiet', url])
            
            self.process = subprocess.Popen(cmd)
            self.add_to_history(url)
            self.update_ui_state(is_playing=True)
            self.status_var.set("Playing video...")
            
        except Exception as e:
            self.logger.error(f"Playback error: {e}")
            messagebox.showerror("Playback Error", str(e))
    
    def stop_video(self):
        """Stop current video playback"""
        if self.process:
            try:
                self.logger.info("Stopping video playback")
                self.process.terminate()
                self.process = None
            except Exception as e:
                self.logger.error(f"Error stopping video: {e}")
        
        self.update_ui_state(is_playing=False)
        self.status_var.set("Ready")
    
    def check_video_status(self):
        """Periodically check if video is still playing"""
        if self.process:
            if self.process.poll() is not None:
                self.logger.info("Video playback completed")
                self.process = None
                self.update_ui_state(is_playing=False)
                self.status_var.set("Ready")
        
        self.root.after(1000, self.check_video_status)
    
    def update_ui_state(self, is_playing):
        """Update UI elements based on playback state"""
        if is_playing:
            self.play_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.url_entry.config(state=tk.DISABLED)
            self.paste_btn.config(state=tk.DISABLED)
            self.settings_btn.config(state=tk.DISABLED)
            self.url_history_combo.config(state=tk.DISABLED)
        else:
            self.play_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.url_entry.config(state=tk.NORMAL)
            self.paste_btn.config(state=tk.NORMAL)
            self.settings_btn.config(state=tk.NORMAL)
            self.url_history_combo.config(state="readonly")
    
    def open_settings(self):
        """Open settings dialog"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x280")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        frame = ttk.Frame(settings_window, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        
        # MPV Path
        ttk.Label(frame, text="MPV Player Path:").grid(row=0, column=0, sticky="w", pady=8)
        mpv_path_var = tk.StringVar(value=self.mpv_path)
        mpv_entry = ttk.Entry(frame, textvariable=mpv_path_var)
        mpv_entry.grid(row=0, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_file(mpv_path_var)).grid(row=0, column=2, padx=4)
        
        # Log Directory
        ttk.Label(frame, text="Log Directory:").grid(row=1, column=0, sticky="w", pady=8)
        log_dir_var = tk.StringVar(value=self.log_dir)
        log_dir_entry = ttk.Entry(frame, textvariable=log_dir_var)
        log_dir_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=8)
        ttk.Button(frame, text="Browse", command=lambda: self.browse_directory(log_dir_var)).grid(row=1, column=2, padx=4)
        
        # Max History
        ttk.Label(frame, text="Max History Items:").grid(row=2, column=0, sticky="w", pady=8)
        max_history_var = tk.StringVar(value=str(self.max_history))
        max_history_entry = ttk.Entry(frame, textvariable=max_history_var, width=10)
        max_history_entry.grid(row=2, column=1, sticky="w", padx=8, pady=8)
        
        # Clear History Button
        ttk.Button(frame, text="Clear History", command=self.clear_history).grid(row=3, column=0, pady=15)
        
        # Save Button
        ttk.Button(frame, text="Save Settings", command=lambda: self.save_settings(
            mpv_path_var.get(),
            log_dir_var.get(),
            max_history_var.get(),
            settings_window
        )).grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
    
    def browse_file(self, string_var):
        """Browse for file and update StringVar"""
        filepath = filedialog.askopenfilename(
            title="Select MPV Player Executable",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if filepath:
            string_var.set(filepath)
    
    def browse_directory(self, string_var):
        """Browse for directory and update StringVar"""
        directory = filedialog.askdirectory(title="Select Log Directory")
        if directory:
            string_var.set(directory)
    
    def save_settings(self, mpv_path, log_dir, max_history, window):
        """Save settings and close window"""
        try:
            self.mpv_path = mpv_path
            self.log_dir = log_dir
            
            try:
                self.max_history = int(max_history)
            except ValueError:
                messagebox.showerror("Error", "Max history must be a number")
                return
            
            self.save_config()
            self.logger.info("Settings saved successfully")
            window.destroy()
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def clear_history(self):
        """Clear URL history"""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear all history?"):
            self.history = {}
            self.save_history()
            self.url_history_combo['values'] = []
            self.logger.info("History cleared")
    
    def on_closing(self):
        """Handle window closing event"""
        self.logger.info("Application shutting down")
        self.stop_video()
        self.root.destroy()
    
    def run(self):
        """Start the GUI application"""
        self.setup_text_handler()
        self.root.mainloop()


def main():
    app = YouTubePlayerApp()
    app.run()


if __name__ == "__main__":
    main()