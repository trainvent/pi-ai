# Pi AI voice assistant

Pipecat 1.12.0 + OpenAI Realtime, using the working Voice HAT audio settings in
[STRATEGY.md](STRATEGY.md). Requires Python 3.11 or 3.12 (`audioop` is removed in 3.13).
Dependencies are installed in `.venv` on this Pi.

## Run the first conversation

```bash
cd ~/pi-ai
cp -n .env.example .env
chmod 600 .env
nano .env
```

Enter your OpenAI API key in `.env`, then run:

```bash
.venv/bin/python assistant.py
```

Speak when the program says it is listening. OpenAI detects speech turns and
speaks the reply. Ctrl+C stops; the session automatically stops after 60 seconds.
Microphone audio is sent to OpenAI during the session, with billed API usage.
The API key stays in the ignored `.env` file; do not paste it into chat.

Configuration: `ALSA_DEVICE=hw:0,0`, `SESSION_SECONDS=60`,
`OUTPUT_VOLUME=0.15`, `OPENAI_REALTIME_MODEL=gpt-realtime`.
Check `arecord -l` and `aplay -l` if card numbering changes.

The ALSA adapter selects the microphone's left channel, converts 48 kHz stereo
S32_LE to 24 kHz mono PCM16, and converts replies back to 48 kHz stereo S32_LE.
No global ALSA or boot settings are changed. Capture is replaced with silence
while replies play and for at least 0.5 seconds afterward to block speaker echo.
Wait until each reply finishes, then pause briefly before speaking. Speaking
over the assistant is intentionally ignored. This is not acoustic echo cancellation.

This starter uses manual activation. Add local wake-word detection and return
to standby after the live conversation test succeeds. “Hey ChatGPT” requires
a custom wake-word model.

To reinstall dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

References: [Pipecat](https://github.com/pipecat-ai/pipecat),
[OpenAI Realtime](https://developers.openai.com/api/docs/guides/realtime).
