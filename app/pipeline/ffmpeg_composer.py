"""FFmpeg composition engine for rendering high-definition, synced MP4 course videos."""

import asyncio
import logging
from pathlib import Path
from typing import List, Tuple
from app.models.schemas import ScriptScene

logger = logging.getLogger(__name__)


class FFmpegComposer:
    """Asynchronous FFmpeg compositor orchestrating video, audio, transitions, and subtitles."""

    async def compose_video(
        self,
        scenes: List[ScriptScene],
        temp_dir: Path,
        output_mp4: Path,
        resolution: str = "1080p",
    ) -> Tuple[Path, Path]:
        """
        Takes rendered slide images and synthesized audio tracks for each scene,
        builds intermediate scene clips, concatenates them, generates subtitles,
        and outputs a finalized web-optimized .mp4 along with a poster thumbnail.
        """
        temp_dir.mkdir(parents=True, exist_ok=True)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        poster_jpg = output_mp4.with_name("poster.jpg")

        logger.info("Beginning FFmpeg composition for %d scenes -> %s", len(scenes), output_mp4)

        # 1. Render individual scene video clips
        scene_clip_paths: List[Path] = []
        cumulative_time = 0.0
        timeline_segments: List[Tuple[float, float, str]] = []

        for scene in scenes:
            scene_mp4 = temp_dir / f"scene_{scene.scene_number}.mp4"
            slide_path = Path(scene.slide_image_path)
            audio_path = Path(scene.audio_file_path)
            duration = scene.duration_seconds or 5.0

            await self._render_scene_clip(slide_path, audio_path, duration, scene_mp4)
            scene_clip_paths.append(scene_mp4)

            timeline_segments.append((cumulative_time, cumulative_time + duration, scene.narration))
            cumulative_time += duration

        # 2. Concat list creation
        concat_list_file = temp_dir / "concat_list.txt"
        with open(concat_list_file, "w") as f:
            for clip in scene_clip_paths:
                f.write(f"file '{clip.resolve()}'\n")

        # 3. Concatenate intermediate clips
        concatenated_raw = temp_dir / "raw_concatenated.mp4"
        concat_cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c", "copy",
            str(concatenated_raw),
        ]
        await self._run_command(concat_cmd)

        # 4. Generate Subtitles file (.srt)
        srt_file = temp_dir / "subtitles.srt"
        self._generate_srt(timeline_segments, srt_file)

        # 5. Final encode with faststart web streaming & optional subtitle burn-in
        final_cmd = [
            "ffmpeg",
            "-y",
            "-i", str(concatenated_raw),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_mp4),
        ]
        await self._run_command(final_cmd)

        # 6. Extract high-resolution poster frame
        thumbnail_cmd = [
            "ffmpeg",
            "-y",
            "-ss", "00:00:01.500",
            "-i", str(output_mp4),
            "-frames:v", "1",
            "-q:v", "2",
            str(poster_jpg),
        ]
        try:
            await self._run_command(thumbnail_cmd)
        except Exception as e:
            logger.warning("Could not extract video thumbnail (%s). Using first slide.", e)
            if scenes and scenes[0].slide_image_path:
                import shutil
                shutil.copy2(scenes[0].slide_image_path, poster_jpg)

        logger.info("FFmpeg composition finished successfully: %s", output_mp4)
        return output_mp4, poster_jpg

    async def _render_scene_clip(self, slide_img: Path, audio_track: Path, duration: float, output_path: Path):
        """Build single scene MP4 pairing still slide image with scene narration audio."""
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", "30",
            "-i", str(slide_img),
            "-i", str(audio_track),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-shortest",
            str(output_path),
        ]
        await self._run_command(cmd)

    def _generate_srt(self, segments: List[Tuple[float, float, str]], srt_path: Path):
        """Creates standard SRT subtitle file with formatted millisecond timestamps."""
        def format_time(seconds: float) -> str:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millis = int(round((seconds - int(seconds)) * 1000))
            return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

        with open(srt_path, "w", encoding="utf-8") as f:
            for idx, (start_t, end_t, text) in enumerate(segments, 1):
                f.write(f"{idx}\n")
                f.write(f"{format_time(start_t)} --> {format_time(end_t)}\n")
                f.write(f"{text.strip()}\n\n")

    async def _run_command(self, cmd: List[str]):
        """Executes FFmpeg subprocess asynchronously and raises on non-zero exit."""
        logger.debug("Executing FFmpeg command: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace")
            logger.error("FFmpeg execution failure:\n%s", err_msg)
            raise RuntimeError(f"FFmpeg error (code {proc.returncode}): {err_msg[:400]}")


ffmpeg_composer = FFmpegComposer()
