# Video Intelligence

NovaBiz Pro Studio now has a real video-understanding workflow.

## Environment

Add to `.env`:

```env
VISION_API_KEY=your_key_here
VISION_API_URL=https://api.openai.com/v1/chat/completions
VISION_MODEL=gpt-4.1-mini
```

`VISION_API_URL` and `VISION_MODEL` are optional. The service expects an OpenAI-compatible chat-completions endpoint that accepts image inputs.

## What it does

1. Receives a Telegram video.
2. Reads duration and resolution with ffprobe.
3. Samples real frames with FFmpeg.
4. Sends the frames to the configured multimodal model.
5. Returns topic, audience, tone, Caption, Bio, Hook, CTA and up to five relevant hashtags.
6. Sends a suggested cover frame back to Telegram.

If `VISION_API_KEY` is missing, the bot fails the job cleanly and refunds the user's credit instead of pretending that AI analysis happened.
