"""Text-to-Speech (TTS) synthesis module supporting edge-tts and OpenAI TTS."""

import asyncio
import logging
from pathlib import Path
from app.config import settings
from app.models.schemas import ScriptScene

logger = logging.getLogger(__name__)


class TTSSynthesizer:
    """Handles real neural speech synthesis and audio duration probing per scene."""

    def __init__(self):
        self.default_voice = settings.TTS_VOICE

    async def synthesize_scene(self, scene: ScriptScene, output_path: Path, voice: str | None = None) -> float:
        """
        Synthesizes spoken narration for a scene and returns its precise duration in seconds.
        Raises an error if synthesis fails—no fake audio tones.
        """
        chosen_voice = voice or self.default_voice
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text = scene.narration.strip()

        if not text:
            raise ValueError(f"Scene {scene.scene_number} has empty narration text.")

        logger.info(
            "Synthesizing scene %d voiceover (%d chars) using '%s' voice [%s]",
            scene.scene_number,
            len(text),
            settings.TTS_PROVIDER,
            chosen_voice,
        )

        if settings.TTS_PROVIDER == "edge_tts":
            return await self._synthesize_edge_tts(text, scene, output_path, chosen_voice)
        elif settings.TTS_PROVIDER == "openai":
            return await self._synthesize_openai_tts(text, scene, output_path)
        else:
            raise ValueError(
                f"Unsupported TTS provider '{settings.TTS_PROVIDER}'. Configure 'edge_tts' or 'openai'."
            )

    async def _synthesize_edge_tts(
        self, text: str, scene: ScriptScene, output_path: Path, voice: str
    ) -> float:
        """Synthesizes neural speech using edge-tts."""
        import edge_tts

        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(output_path))
        except Exception as e:
            logger.error("edge-tts synthesis failed for scene %d: %s", scene.scene_number, e)
            raise RuntimeError(f"Edge-TTS synthesis error on scene {scene.scene_number}: {e}") from e

        duration = await self._probe_audio_duration(output_path)
        scene.audio_file_path = str(output_path)
        scene.duration_seconds = duration
        return duration

    async def _synthesize_openai_tts(
        self, text: str, scene: ScriptScene, output_path: Path
    ) -> float:
        """Synthesizes neural speech using OpenAI Audio API."""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when TTS_PROVIDER=openai.")

        from openai import AsyncOpenAI

        try:
            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            response = await client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
            )
            await asyncio.to_thread(response.stream_to_file, str(output_path))
        except Exception as e:
            logger.error("OpenAI TTS failed for scene %d: %s", scene.scene_number, e)
            raise RuntimeError(f"OpenAI TTS synthesis error on scene {scene.scene_number}: {e}") from e

        duration = await self._probe_audio_duration(output_path)
        scene.audio_file_path = str(output_path)
        scene.duration_seconds = duration
        return duration

    async def _probe_audio_duration(self, audio_file: Path) -> float:
        """Probes the audio file using ffprobe to obtain exact duration in seconds."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_file),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode(errors="replace")
            raise RuntimeError(f"ffprobe failed to probe audio duration ({audio_file}): {err}")

        duration_str = stdout.decode().strip()
        duration = round(float(duration_str), 2)
        if duration <= 0:
            raise RuntimeError(f"Audio file {audio_file} generated with 0 second duration.")
        return duration


tts_synthesizer = TTSSynthesizer()
