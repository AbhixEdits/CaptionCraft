import os, json, uuid, subprocess, shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
OUTPUTS = ROOT / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)
ALLOWED = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1 GB local-use limit

def has_ffmpeg():
    return shutil.which("ffmpeg") is not None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/upload", methods=["POST"])
def upload():
    f = request.files.get("media")
    if not f or not f.filename:
        return jsonify(error="Choose a video or audio file first."), 400
    suffix = Path(secure_filename(f.filename)).suffix.lower()
    if suffix not in ALLOWED:
        return jsonify(error="Unsupported format. Try MP4, MOV, MKV, WEBM, MP3, WAV, M4A, AAC, OGG or FLAC."), 400
    job = uuid.uuid4().hex[:12]
    dest = UPLOADS / f"{job}{suffix}"
    f.save(dest)
    return jsonify(job=job, filename=f.filename, kind="video" if suffix in {".mp4",".mov",".mkv",".webm"} else "audio")

@app.route("/api/transcribe/<job>", methods=["POST"])
def transcribe(job):
    files = list(UPLOADS.glob(job + ".*"))
    if not files:
        return jsonify(error="Upload not found. Please upload the file again."), 404
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return jsonify(error="Transcription package is missing. Run: pip install -r requirements.txt"), 500
    data = request.get_json(silent=True) or {}
    model_size = data.get("model", "small")
    # CPU/int8 is the most broadly compatible local default.
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(files[0]), beam_size=5, vad_filter=True)
        rows = []
        for i, seg in enumerate(segments):
            rows.append({"id": i + 1, "start": round(seg.start, 2), "end": round(seg.end, 2),
                         "original": seg.text.strip(), "caption": seg.text.strip()})
        return jsonify(language=info.language, language_probability=round(info.language_probability, 3),
                       segments=rows, count=len(rows))
    except Exception as e:
        return jsonify(error=f"Transcription failed: {e}"), 500

@app.route("/api/hinglish", methods=["POST"])
def hinglish():
    data = request.get_json(force=True)
    segments = data.get("segments", [])
    source_lang = data.get("language", "auto")
    try:
        from deep_translator import GoogleTranslator
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
        out = []
        # Translate each segment into Hindi, then write Hindi in Latin letters.
        translator = GoogleTranslator(source="auto", target="hi")
        for s in segments:
            text = (s.get("original") or "").strip()
            if not text:
                out.append(s); continue
            try:
                hindi = translator.translate(text)
                roman = transliterate(hindi, sanscript.DEVANAGARI, sanscript.ITRANS)
                # ITRANS has scholarly symbols; simplify common patterns to more readable Roman Hindi.
                replacements = [
                    ("aa", "aa"), ("RRi", "ri"), ("R^i", "ri"), ("shh", "sh"),
                    ("Sh", "sh"), ("sh", "sh"), ("chh", "chh"), ("JN", "gy"),
                    ("~N", "n"), ("M", "n"), ("H", "h"), ("^", "")
                ]
                for a, b in replacements: roman = roman.replace(a, b)
                s["caption"] = roman
            except Exception:
                s["caption"] = text
            out.append(s)
        return jsonify(segments=out, note="Automatic translation/transliteration is a best-effort draft. Review names, slang and context.")
    except ImportError:
        return jsonify(error="Hinglish dependencies missing. Run: pip install -r requirements.txt"), 500
    except Exception as e:
        return jsonify(error=f"Hinglish conversion failed: {e}"), 500

@app.route("/api/export", methods=["POST"])
def export():
    data = request.get_json(force=True)
    job = data.get("job", "")
    files = list(UPLOADS.glob(job + ".*"))
    if not files:
        return jsonify(error="Upload not found."), 404
    if not has_ffmpeg():
        return jsonify(error="FFmpeg is required for video export. Install FFmpeg and restart CaptionCraft."), 500
    segments = data.get("segments", [])
    style = data.get("style", {})
    is_video = files[0].suffix.lower() in {".mp4",".mov",".mkv",".webm"}
    if not is_video:
        return jsonify(error="This upload is audio. Captions can be edited, but burned-in video export needs a video file."), 400

    def ass_time(seconds):
        cs = max(0, int(float(seconds) * 100))
        h, rem = divmod(cs, 360000); m, rem = divmod(rem, 6000); sec, centi = divmod(rem, 100)
        return f"{h}:{m:02d}:{sec:02d}.{centi:02d}"
    def ass_escape(s):
        return str(s).replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")
    # ASS uses BGR color format & alpha. 
    color_map = {"white":"&H00FFFFFF","yellow":"&H0000D7FF","cyan":"&H00FFFF00","pink":"&H00C060FF","green":"&H0000FF70"}
    color = color_map.get(style.get("color", "yellow"), "&H0000D7FF")
    font = style.get("font", "Arial").replace(",", "")
    size = int(style.get("size", 48))
    bold = -1 if style.get("template") in ("bold", "neon", "outline") else 0
    outline = 3 if style.get("template") in ("outline", "neon") else 2
    alignment = 8 if style.get("position") == "top" else (5 if style.get("position") == "middle" else 2)
    ass = OUTPUTS / f"{job}_captions.ass"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: 1920", "PlayResY: 1080", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font},{size},{color},&H000000FF,&H00101010,&H99000000,{bold},0,0,0,100,100,0,0,1,{outline},1,{alignment},60,60,55,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    for s in segments:
        if not str(s.get("caption","")).strip(): continue
        lines.append(f"Dialogue: 0,{ass_time(s.get('start',0))},{ass_time(s.get('end',0))},Default,,0,0,0,,{ass_escape(s['caption'])}")
    ass.write_text("\n".join(lines), encoding="utf-8")
    out = OUTPUTS / f"{job}_captioned.mp4"
    # ffmpeg subtitle filter paths need escaping for Windows drive/colon and apostrophes.
    ass_path = str(ass.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    cmd = ["ffmpeg", "-y", "-i", str(files[0]), "-vf", f"subtitles='{ass_path}'", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(out)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if p.returncode != 0:
            return jsonify(error="FFmpeg export failed: " + (p.stderr[-1200:] or "Unknown error")), 500
        return jsonify(url=f"/outputs/{out.name}", filename=out.name)
    except subprocess.TimeoutExpired:
        return jsonify(error="Export timed out. Try a shorter/lower-resolution video."), 500

@app.route("/outputs/<path:name>")
def output_file(name):
    return send_from_directory(OUTPUTS, name, as_attachment=True)

@app.errorhandler(413)
def too_large(_):
    return jsonify(error="File is over the 1 GB limit."), 413

if __name__ == "__main__":
    print("CaptionCraft running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
