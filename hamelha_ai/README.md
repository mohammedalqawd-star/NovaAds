# Hamelha AI Studio 🚀

Telegram video automation platform.

## Included now
- Text → vertical MP4 video with Arabic/Unicode text slides.
- Images → slideshow video (9:16).
- Video → Shorts/Reels 9:16 conversion.
- Video → MP3 extraction engine.
- URL → video download through yt-dlp.
- User credits and job history in SQLite.
- Docker image with FFmpeg.

## Run
1. Install Python 3.12+ and FFmpeg.
2. `pip install -r hamelha_ai/requirements.txt`
3. Copy `.env.example` to `.env` and set `BOT_TOKEN` and `ADMIN_ID`.
4. Run: `python -m hamelha_ai.bot`

## Production
Use a VPS or a cloud worker/container service. GitHub stores the code; it does not itself keep a Telegram bot running 24/7. A free tier may sleep, have CPU/storage limits, or expire, so 24/7 availability is not guaranteed by the free tier.

## Monetization
The code has a credit system. Add your approved payment method and package amounts in a payment handler before accepting money. Do not put payment credentials or bot tokens in GitHub files; use environment secrets.

## Important
Only download or process content you have the right to use. Platform rules and copyright restrictions still apply.
