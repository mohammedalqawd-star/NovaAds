# Hamelha AI Studio 🚀

Telegram video studio: text → video, images → video, video formatting, MP3 extraction and URL downloads.

## Features
- ✍️ Text → vertical video with Arabic TTS
- 🖼️ Up to 40 images → MP4
- 🎬 Shorts 9:16 / square 1:1 / landscape processing
- 🎵 Video → MP3
- ⬇️ URL → video with yt-dlp
- 🎁 Free credits
- 👥 Referral code storage
- 📊 Admin statistics
- 🔐 Secrets via environment variables

## Run
Install Python 3.11+, FFmpeg, then:

```bash
pip install -r hamelha_ai/requirements.txt
python -m hamelha_ai.bot
```

Required environment variables:
- `BOT_TOKEN` — Telegram BotFather token
- `ADMIN_ID` — your Telegram numeric ID
- Optional: `FREE_CREDITS`, `DATABASE_URL`, `WORK_DIR`, `MAX_UPLOAD_MB`, `FFMPEG`

Never commit `.env`, bot tokens, payment credentials, or private keys.

## Production
GitHub stores the code; it does not itself keep a Telegram bot running 24/7. Use a compatible always-on server/container worker. Free hosting tiers can sleep or impose CPU, storage, runtime, or bandwidth limits.

## Monetization
The project has credits and referral infrastructure. A real payment handler should only be enabled after choosing an approved payment method; payment credentials belong in environment secrets, never in GitHub.

## Content
Only download/process content you have the right to use and follow the rules of the source platforms.
