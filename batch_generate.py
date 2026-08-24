#!/usr/bin/env bash
# Batch generator: daftar topik -> script(LLM/9router) -> video -> metadata sosial -> copy ke Downloads Windows
# Usage:
#   echo -e "Why waking up early changes your brain\\nThe deep ocean: Earth's last frontier" > topics.txt
#   uv run python batch_generate.py --file topics.txt --lang en --platform facebook_reels
#   uv run python batch_generate.py --subject "Manfaat tidur cukup" --lang id
import argparse, json, shutil, subprocess, sys, time, unicodedata
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

API = "http://127.0.0.1:8080/api/v1"
WIN_DL = Path("/mnt/c/Users/mdr07/Downloads/MoneyPrinterTurbo-hasil")
OUT = Path(__file__).parent / "storage" / "batch"
VOICES = {
    "en": "en-US-JennyNeural-Female",
    "id": "id-ID-GadisNeural-Female",
}
LANG_NAME = {"en": "English", "id": "Indonesian"}

def api(path, payload=None, timeout=180):
    req = Request(
        API + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(req, timeout=timeout) as r:
        return json.load(r)

def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "-".join(c for c in text.lower().split() if c.isalnum())[:60] or f"topic-{int(time.time())}"

def wait_task(task_id):
    while True:
        time.sleep(15)
        t = api(f"/tasks/{task_id}")["data"]
        state = t["state"]
        if state == 1:
            name = Path(t["videos"][0]).name          # API returns URI -> take filename
            local = Path(__file__).parent / "storage" / "tasks" / task_id / name
            if not local.exists():
                raise RuntimeError(f"rendered file missing: {local}")
            return local
        if state == 0:
            raise RuntimeError(f"task failed stage={t.get('failed_stage')} err={t.get('error')}")
        print(f"  progress {t['progress']}%", flush=True)

def process(subject, lang, platform, aspect):
    slug = slugify(subject)
    dest = OUT / slug
    if (dest / "final.mp4").exists():
        print(f"skip (sudah ada): {slug}")
        return
    print(f"[{subject}] generate script...", flush=True)
    script = api("/scripts", {
        "video_subject": subject,
        "video_language": LANG_NAME[lang],
        "paragraph_number": 1,
    })["data"]["video_script"]

    print(f"[{subject}] submit video task...", flush=True)
    task_id = api("/videos", {
        "video_subject": subject,
        "video_script": script,
        "voice_name": VOICES[lang],
        "video_aspect": aspect,
        "video_clip_duration": 3,
        "subtitle_enabled": True,
        "video_count": 1,
    })["data"]["task_id"]

    print(f"[{subject}] rendering task {task_id[:8]}...", flush=True)
    video = wait_task(task_id)

    print(f"[{subject}] social metadata ({platform})...", flush=True)
    meta = api("/social-metadata", {
        "video_subject": subject,
        "video_script": script,
        "language": LANG_NAME[lang],
        "platform": platform,
    })["data"]

    dest.mkdir(parents=True, exist_ok=True)
    final = dest / "final.mp4"
    shutil.copy(video, final)
    (dest / "metadata.json").write_text(json.dumps(
        {"subject": subject, "script": script, "task_id": task_id, **meta},
        ensure_ascii=False, indent=2))

    if WIN_DL.exists():
        win = WIN_DL / slug
        win.mkdir(exist_ok=True)
        shutil.copy(final, win / "final.mp4")
        shutil.copy(dest / "metadata.json", win / "metadata.json")
    print(f"DONE {dest}", flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="file berisi topik, satu per baris")
    ap.add_argument("--subject", help="satu topik langsung")
    ap.add_argument("--lang", default="en", choices=["en", "id"])
    ap.add_argument("--aspect", default="9:16", choices=["9:16", "16:9", "4:3"])
    ap.add_argument("--platform", default="facebook_reels",
                    choices=["tiktok", "youtube_shorts", "instagram_reels", "facebook_reels"])
    a = ap.parse_args()
    subjects = []
    if a.file:
        subjects += [l.strip() for l in Path(a.file).read_text().splitlines() if l.strip()]
    if a.subject:
        subjects.append(a.subject)
    if not subjects:
        sys.exit("berikan --file atau --subject")
    for s in subjects:
        try:
            process(s, a.lang, a.platform, a.aspect)
        except Exception as e:
            print(f"FAIL [{s}]: {e}", flush=True)

if __name__ == "__main__":
    main()
