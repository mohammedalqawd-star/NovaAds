import asyncio, os, subprocess, uuid, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from .config import settings

def ensure_dirs(): Path(settings.work_dir).mkdir(parents=True, exist_ok=True)
def run(cmd, timeout=900): return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
def font(size=54):
    for name in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try: return ImageFont.truetype(name,size)
        except Exception: pass
    return ImageFont.load_default()
def make_card(text,path,title="Hamelha AI"):
    im=Image.new("RGB",(1080,1920),(18,18,24)); dr=ImageDraw.Draw(im)
    for y in range(0,1920,80):
        s=18+int(10*y/1920); dr.rectangle((0,y,1080,y+80),fill=(s,s,s+8))
    ft=font(66); b=dr.textbbox((0,0),title,font=ft); dr.text(((1080-(b[2]-b[0]))/2,230),title,font=ft,fill="white")
    f=font(50); lines=[]; cur=""
    for w in text.split():
        t=(cur+" "+w).strip()
        if dr.textbbox((0,0),t,font=f)[2]<900: cur=t
        else: lines.append(cur); cur=w
    if cur: lines.append(cur)
    y=780-len(lines)*35
    for line in lines:
        b=dr.textbbox((0,0),line,font=f); x=(1080-(b[2]-b[0]))/2
        dr.text((x,y),line,font=f,fill="white",stroke_width=2,stroke_fill="black"); y+=82
    im.save(path,quality=92)
async def text_to_video(text,uid,voice=True):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True)
    chunks=[x.strip() for x in text.replace("\r","\n").split("\n") if x.strip()]
    if len(chunks)==1 and len(chunks[0])>180: chunks=textwrap.wrap(chunks[0],180)
    chunks=chunks[:20] or [text]; images=[]
    for i,line in enumerate(chunks):
        p=d/f"s{i:03}.jpg"; make_card(line,p); images.append(p)
    concat=d/"list.txt"; dur=max(2.0,min(5.0,50/max(1,len(images))))
    concat.write_text("\n".join(f"file '{p}'\nduration {dur}" for p in images)+f"\nfile '{images[-1]}'")
    out=d/"text_video.mp4"; r=run([settings.ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    if voice:
        try:
            audio=d/"voice.mp3"; await asyncio.to_thread(lambda:gTTS(text=text,lang="ar").save(str(audio)))
            voiced=d/"text_video_voice.mp4"; r=run([settings.ffmpeg,"-y","-i",str(out),"-i",str(audio),"-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(voiced)])
            if r.returncode==0: out=voiced
        except Exception: pass
    return out
async def images_to_video(paths,uid,duration=3):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); imgs=[]
    for i,p in enumerate(paths[:40]):
        im=Image.open(p).convert("RGB"); im.thumbnail((1040,1800)); c=Image.new("RGB",(1080,1920),(10,10,14)); c.paste(im,((1080-im.width)//2,(1920-im.height)//2)); q=d/f"i{i:03}.jpg"; c.save(q,quality=92); imgs.append(q)
    concat=d/"list.txt"; concat.write_text("\n".join(f"file '{p}'\nduration {duration}" for p in imgs)+f"\nfile '{imgs[-1]}'")
    out=d/"images_video.mp4"; r=run([settings.ffmpeg,"-y","-f","concat","-safe","0","-i",str(concat),"-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return out
async def edit_video(src,uid,mode="shorts",mute=False):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); out=d/"edited.mp4"
    vf="scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" if mode=="shorts" else ("scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2" if mode=="square" else "scale=1280:-2")
    cmd=[settings.ffmpeg,"-y","-i",str(src),"-vf",vf,"-c:v","libx264","-preset","veryfast"]; cmd += ["-an"] if mute else ["-c:a","aac"]; cmd += ["-movflags","+faststart",str(out)]
    r=run(cmd)
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return out
async def extract_audio(src,uid):
    ensure_dirs(); out=Path(settings.work_dir)/str(uid)/f"{uuid.uuid4().hex}.mp3"; r=run([settings.ffmpeg,"-y","-i",str(src),"-vn","-c:a","libmp3lame","-q:a","4",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return out
async def add_caption(src,text,uid):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); cap=d/"caption.txt"; cap.write_text(text,encoding="utf-8"); out=d/"captioned.mp4"
    vf=f"drawtext=textfile='{str(cap)}':fontcolor=white:fontsize=48:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h-220"; r=run([settings.ffmpeg,"-y","-i",str(src),"-vf",vf,"-c:v","libx264","-preset","veryfast","-c:a","aac","-movflags","+faststart",str(out)])
    if r.returncode: raise RuntimeError(r.stderr[-1200:])
    return out
async def download(url,uid):
    ensure_dirs(); d=Path(settings.work_dir)/str(uid)/uuid.uuid4().hex; d.mkdir(parents=True); out=d/"video.%(ext)s"; r=run(["yt-dlp","--no-playlist","-f","bv*+ba/b","--merge-output-format","mp4","-o",str(out),url],timeout=1200)
    if r.returncode: raise RuntimeError(r.stderr[-1800:])
    files=[p for p in d.glob("video.*") if p.suffix.lower() not in (".part",)]
    if not files: raise RuntimeError("لم يتم العثور على الملف الناتج")
    return files[0]
