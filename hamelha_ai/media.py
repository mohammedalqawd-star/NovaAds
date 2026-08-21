import asyncio, os, subprocess, uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from .config import settings

EXT={"video":(".mp4",),"image":(".jpg",".jpeg",".png",".webp")}

def ensure_dirs(): Path(settings.work_dir).mkdir(parents=True, exist_ok=True)

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=900)

async def text_to_video(text, uid):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True)
    lines=[x.strip() for x in text.replace("\r","\n").split("\n") if x.strip()]
    if not lines: lines=[text]
    images=[]
    try: font=ImageFont.truetype("DejaVuSans.ttf",48)
    except: font=ImageFont.load_default()
    for i,line in enumerate(lines[:12]):
        im=Image.new("RGB",(1080,1920)); dr=ImageDraw.Draw(im)
        words=line.split(); rows=[]; cur=""
        for w in words:
            if dr.textbbox((0,0),cur+" "+w,font=font)[2] < 900: cur=(cur+" "+w).strip()
            else: rows.append(cur); cur=w
        if cur: rows.append(cur)
        y=800-len(rows)*35
        for r in rows:
            box=dr.textbbox((0,0),r,font=font); dr.text(((1080-(box[2]-box[0]))/2,y),r,font=font,fill="white",stroke_width=2,stroke_fill="black"); y+=75
        p=d/f"s{i:03}.jpg"; im.save(p,quality=92); images.append(p)
    concat=d/"list.txt"
    dur=max(2.5, min(6.0, 45/max(1,len(images))))
    concat.write_text("\n".join(f"file '{p}'\nduration {dur}" for p in images)+f"\nfile '{images[-1]}'")
    out=d/"text_video.mp4"
    r=run([settings.ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1200:])
    return out

async def images_to_video(paths, uid):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True)
    imgs=[]
    for i,p in enumerate(paths[:30]):
        im=Image.open(p).convert("RGB"); im.thumbnail((1080,1920)); canvas=Image.new("RGB",(1080,1920)); canvas.paste(im,((1080-im.width)//2,(1920-im.height)//2)); q=d/f"i{i:03}.jpg"; canvas.save(q,quality=90); imgs.append(q)
    concat=d/"list.txt"; dur=3
    concat.write_text("\n".join(f"file '{p}'\nduration {dur}" for p in imgs)+f"\nfile '{imgs[-1]}'")
    out=d/"images_video.mp4"; r=run([settings.ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1200:])
    return out

async def edit_video(src, uid, mode="shorts"):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); out=d/"edited.mp4"
    vf="scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" if mode=="shorts" else "scale=1280:-2"
    r=run([settings.ffmpeg,"-y","-i",str(src),"-vf",vf,"-c:v","libx264","-preset","veryfast","-c:a","aac","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1200:])
    return out

async def extract_audio(src, uid):
    ensure_dirs(); out=Path(settings.work_dir)/str(uid)/f"{uuid.uuid4().hex}.mp3"; r=run([settings.ffmpeg,"-y","-i",str(src),"-vn","-c:a","libmp3lame","-q:a","4",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1200:])
    return out

async def download(url, uid):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); out=d/"video.%(ext)s"
    r=run(["yt-dlp","--no-playlist","-f","bv*+ba/b","--merge-output-format","mp4","-o",str(out),url])
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    files=list(d.glob("video.*"));
    if not files: raise RuntimeError("لم يتم العثور على الملف الناتج")
    return files[0]
