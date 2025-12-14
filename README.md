# YouTube Player

A lightweight, user-friendly desktop application for playing YouTube videos directly using mpv.

<img width="702" height="536" alt="screenshot" src="https://github.com/user-attachments/assets/b8635b90-e67f-4576-b5e3-4b3633c513b5" />


## Features

- Play YouTube videos in fullscreen
- Loop playback support
- URL history with quick access
- Clipboard URL paste (Ctrl+V)
- Activity logging
- Auto-update yt-dlp on startup
- Configurable settings

## Requirements

- Python 3.6+
- tkinter (usually included with Python)
- pyperclip

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/gjdragon/youtubePlayer.git
   cd youtube-player
   ```

2. Install Python dependencies:
   ```bash
   pip install pyperclip
   ```

3. **Download and set up media tools:**
   
   Create a `tools/` folder in the project directory and download:
   
   - **mpv**: Download from [mpv.io](https://mpv.io/installation/)
     - Extract and place `mpv.exe` in `tools/`
   
   - **yt-dlp**: Download from [yt-dlp releases](https://github.com/yt-dlp/yt-dlp/releases)
     - Place `yt-dlp.exe` in `tools/`

   Your project structure should look like:
   ```
   youtube-player/
   ├── main.py
   ├── config.ini (auto-created)
   ├── history.json (auto-created)
   ├── logs/ (auto-created)
   └── tools/
       ├── mpv.exe
       └── yt-dlp.exe
   ```

## Usage

Run the application:
```bash
python main.py
```

### Keyboard Shortcuts

- **Ctrl+V** - Paste URL from clipboard
- **Ctrl+P** - Play video
- **Esc** - Stop video

### Settings

Click the **⚙ Settings** button to:
- Configure mpv player path
- Set log directory
- Adjust history size
- Clear history

## Features

- **Auto-update**: yt-dlp is automatically updated on startup
- **Persistent History**: Remembers your recently played URLs
- **Fullscreen Mode**: Play videos in fullscreen by default
- **Loop Playback**: Repeat videos continuously if needed

## Supported URL Formats

- `https://www.youtube.com/watch?v=...`
- `https://youtu.be/...`
- `https://www.youtube.com/shorts/...`
- `https://www.youtube.com/live/...`
- `https://www.youtube.com/playlist?list=...`

## License

MIT License - feel free to use and modify as needed.

## Troubleshooting

**"mpv.exe not found"** - Ensure `mpv.exe` is in the `tools/` directory.

**"yt-dlp.exe not found"** - Ensure `yt-dlp.exe` is in the `tools/` directory.

**Video won't play** - Check the Activity Log for error messages. Verify the URL is a valid YouTube link.
