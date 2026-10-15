# CaptionCraft — private local captioning web app

CaptionCraft runs on your own computer and opens in your browser. It can:
- Accept common video and audio formats
- Transcribe speech with Whisper (timed segments, language detection)
- Create a best-effort Hinglish draft by translating to Hindi and transliterating into Latin letters
- Let you edit caption text and timestamps
- Export `.SRT` subtitles
- Burn styled captions into an MP4 using FFmpeg

## Requirements
- Python 3.10 or newer
- FFmpeg installed and available on your PATH (needed for captioned MP4 export)
- Internet connection for the initial Whisper model download and Hinglish translation

## Start on Windows
1. Extract `CaptionCraft.zip`.
2. Install Python from https://www.python.org/downloads/ (check “Add Python to PATH”).
3. Install FFmpeg and make sure `ffmpeg -version` works in Command Prompt.
4. Open the extracted `captioncraft` folder, click the address bar, type `cmd`, and press Enter.
5. Run:
   ```bat
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python app.py
   ```
6. Open http://127.0.0.1:5000 in your browser. Keep the terminal window open while using it.

## Start on macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000.

## Notes
- This is a private-use starter app, not a hosted public service. It binds to `127.0.0.1`, so it is intended for use on the same computer.
- The first transcription downloads the Whisper `small` model and may take several minutes. It runs on CPU and can be slow on older computers. You can change the model to `base` in `templates/index.html` for faster results or `medium` for potentially better accuracy with more compute.
- Translation/transliteration is best-effort. Hinglish has no single standard spelling; review names, slang, idioms, numbers, and timings before publishing.
- Google translation is an online service; when you click Convert to Hinglish, the text sent for translation leaves your computer. Uploaded media and local transcription are processed locally.
- Audio-only files support transcription and `.SRT` export. Burned-in video export requires a video upload and FFmpeg.
- Fonts available to FFmpeg depend on the fonts installed on your computer. For best results, use a common installed font such as Arial or DejaVu Sans.
