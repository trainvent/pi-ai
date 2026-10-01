"""Manually activated, time-limited Pipecat voice conversation."""
import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.openai.realtime.llm import OpenAIRealtimeLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.workers.runner import WorkerRunner

from audio import PiInput, PiOutput, PlaybackGate


async def converse():
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise SystemExit('Set OPENAI_API_KEY in pi-ai/.env first. Do not paste it into chat.')
    seconds = int(os.getenv('SESSION_SECONDS', '60'))
    volume = float(os.getenv('OUTPUT_VOLUME', '0.15'))
    if not 1 <= seconds <= 600 or not 0 < volume <= 1:
        raise SystemExit('SESSION_SECONDS must be 1–600; OUTPUT_VOLUME must be >0 and <=1.')
    params = TransportParams(audio_in_enabled=True, audio_out_enabled=True,
                             audio_in_sample_rate=24000, audio_out_sample_rate=48000,
                             audio_in_channels=1, audio_out_channels=1)
    device = os.getenv('ALSA_DEVICE', 'hw:0,0')
    service = OpenAIRealtimeLLMService(
        api_key=key,
        settings=OpenAIRealtimeLLMService.Settings(
            model=os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime'),
            system_instruction=(
                'You are a helpful voice assistant. Respond in the language the user speaks. '
                'The user cannot interrupt you while you speak, so keep replies short. '
                'By default, answer in one or two short sentences, aiming for at most 40 words. '
                'Give the direct answer first. Skip introductions, repetition, and unnecessary detail. '
                'Only give a longer explanation when the user explicitly asks for details. '
                'For instructions, give the next useful step and wait for the user before continuing. '
                'If clarification is needed, ask one short question. '
                'Include essential safety information when needed, even if it takes a few extra words.'
            )
        ),
    )
    user, assistant = LLMContextAggregatorPair(LLMContext())
    gate = PlaybackGate()
    worker = PipelineWorker(
        Pipeline([PiInput(params, device, gate), user, service,
                  PiOutput(params, device, volume, gate), assistant]),
        params=PipelineParams(audio_in_sample_rate=24000, audio_out_sample_rate=48000),
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner()
    await runner.add_workers(worker)

    async def deadline():
        await asyncio.sleep(seconds)
        print('Session finished.')
        await runner.cancel()

    timer = asyncio.create_task(deadline())
    print(f'Listening now for up to {seconds} seconds. Speak; Ctrl+C stops. Audio goes to OpenAI.')
    try:
        await runner.run()
    finally:
        timer.cancel()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    load_dotenv(Path(__file__).with_name('.env'))
    asyncio.run(converse())
