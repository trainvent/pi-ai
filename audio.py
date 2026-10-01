"""ALSA adapter for the verified Voice HAT format (Python 3.11/3.12)."""
import asyncio
import audioop
import time
from contextlib import suppress

from pipecat.frames.frames import InputAudioRawFrame, BotStartedSpeakingFrame, BotStoppedSpeakingFrame
from pipecat.transports.base_input import BaseInputTransport
from pipecat.transports.base_output import BaseOutputTransport


def microphone_pcm(raw):
    # Keep the left channel at full amplitude; the right channel is silent.
    mono = audioop.tomono(raw, 4, 1, 0)
    return audioop.lin2lin(mono, 4, 2)


def speaker_pcm(raw, volume):
    quiet = audioop.mul(raw, 2, volume)
    return audioop.tostereo(audioop.lin2lin(quiet, 2, 4), 4, 1, 1)


async def close_process(proc):
    if proc is not None and proc.returncode is None:
        with suppress(ProcessLookupError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 2)
        except asyncio.TimeoutError:
            with suppress(ProcessLookupError):
                proc.kill()
            await proc.wait()


async def recorder(device):
    return await asyncio.create_subprocess_exec(
        'arecord', '-q', '-D', device, '-t', 'raw', '-r', '48000',
        '-f', 'S32_LE', '-c', '2', stdout=asyncio.subprocess.PIPE,
    )


class PlaybackGate:
    """Mute capture during replies, including buffered playback and echo tail."""
    def __init__(self):
        self.speaking = False
        self.until = 0.0

    def muted(self):
        return self.speaking or time.monotonic() < self.until


class PiInput(BaseInputTransport):
    def __init__(self, params, device, gate=None):
        super().__init__(params)
        self.device = device
        self.proc = self.reader = None
        self.gate = gate or PlaybackGate()
        self.closing = False

    async def process_frame(self, frame, direction):
        if isinstance(frame, BotStartedSpeakingFrame):
            self.gate.speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.gate.speaking = False
            self.gate.until = max(self.gate.until, time.monotonic() + 0.5)
        await super().process_frame(frame, direction)

    async def stop(self, frame):
        self.closing = True
        await super().stop(frame)

    async def cancel(self, frame):
        self.closing = True
        await super().cancel(frame)

    async def start(self, frame):
        await super().start(frame)
        self.proc = await recorder(self.device)
        await self.set_transport_ready(frame)
        self.reader = self.create_task(self.read_audio())

    async def read_audio(self):
        state = None
        try:
            while True:
                raw = await self.proc.stdout.readexactly(960 * 8)
                pcm, state = audioop.ratecv(
                    microphone_pcm(raw), 2, 1, 48000, self.sample_rate, state
                )
                # Continue draining ALSA, but send silence instead of speaker echo.
                # This also lets server VAD finish any previous speech turn.
                if self.gate.muted():
                    pcm = bytes(len(pcm))
                await self.push_audio_frame(InputAudioRawFrame(
                    audio=pcm, sample_rate=self.sample_rate, num_channels=1
                ))
        except asyncio.IncompleteReadError:
            if not self.closing:
                await self.push_error(error_msg='ALSA capture stopped; check device and permissions.',
                                      force_treat_as_permanent=True)

    async def cleanup(self):
        self.closing = True
        if self.reader:
            await self.cancel_task(self.reader)
        await close_process(self.proc)
        await super().cleanup()


class PiOutput(BaseOutputTransport):
    def __init__(self, params, device, volume, gate=None):
        super().__init__(params)
        self.device, self.volume = device, volume
        self.proc = None
        self.gate = gate or PlaybackGate()

    async def start(self, frame):
        await super().start(frame)
        self.proc = await asyncio.create_subprocess_exec(
            'aplay', '-q', '-D', self.device, '-t', 'raw', '-r', '48000',
            '-f', 'S32_LE', '-c', '2', stdin=asyncio.subprocess.PIPE,
            limit=16384,
        )
        await self.set_transport_ready(frame)

    async def write_audio_frame(self, frame):
        # Cover audio already in the pipe/device even if Pipecat declares a stop.
        duration = len(frame.audio) / (48000 * 2)
        now = time.monotonic()
        self.gate.until = max(now, self.gate.until - 0.5) + duration + 0.5
        self.proc.stdin.write(speaker_pcm(frame.audio, self.volume))
        await self.proc.stdin.drain()
        return True

    async def cleanup(self):
        await super().cleanup()
        await close_process(self.proc)
