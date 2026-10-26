"""End-to-end pipeline orchestrator managing stage transitions, progress emission, and error handling."""

import logging
from pathlib import Path
from typing import Any, Dict
from app.config import settings
from app.core.events import event_bus
from app.core.storage import storage_manager
from app.models.schemas import PipelineProgress, TaskStage
from app.pipeline.script_generator import script_generator
from app.pipeline.tts_synthesizer import tts_synthesizer
from app.pipeline.visual_generator import visual_generator
from app.pipeline.ffmpeg_composer import ffmpeg_composer

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Coordinates execution across LLM script generation, TTS, visual rendering, and FFmpeg."""

    async def run(self, task_payload: Dict[str, Any]):
        """Executes the complete media generation pipeline for a given job payload."""
        task_id = task_payload["task_id"]
        topic = task_payload["topic"]
        target_scenes = task_payload.get("target_scenes", 3)
        voice = task_payload.get("voice")
        resolution = task_payload.get("resolution", "1080p")

        temp_dir = settings.TEMP_DIR / task_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting pipeline execution for task '%s' [Topic: %s]", task_id, topic)

        try:
            # ---------------------------------------------------------
            # Stage 1: Script & Storyboard Generation (LLM)
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.SCRIPT_GENERATION,
                progress_percent=15,
                message=f"Generating educational curriculum & structured storyboard for '{topic}'...",
            )
            script = await script_generator.generate(topic=topic, target_scenes=target_scenes)

            # ---------------------------------------------------------
            # Stage 2: Audio / Voiceover Synthesis (TTS)
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.AUDIO_SYNTHESIS,
                progress_percent=30,
                message=f"Synthesizing voice narration for {len(script.scenes)} scenes...",
            )
            for idx, scene in enumerate(script.scenes, start=1):
                audio_file = temp_dir / f"narration_scene_{scene.scene_number}.mp3"
                duration = await tts_synthesizer.synthesize_scene(scene, audio_file, voice=voice)
                pct = 30 + int((idx / len(script.scenes)) * 20)
                await self._emit(
                    task_id=task_id,
                    topic=topic,
                    stage=TaskStage.AUDIO_SYNTHESIS,
                    progress_percent=pct,
                    message=f"Synthesized scene {idx}/{len(script.scenes)} narration ({duration:.1f}s)",
                )

            # ---------------------------------------------------------
            # Stage 3: Slide & Visual Generation (Pillow)
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.SCENE_RENDERING,
                progress_percent=55,
                message="Rendering 1080p high-definition slide graphics and typography...",
            )
            for idx, scene in enumerate(script.scenes, start=1):
                slide_file = temp_dir / f"slide_scene_{scene.scene_number}.png"
                visual_generator.render_scene_slide(
                    scene=scene,
                    total_scenes=len(script.scenes),
                    topic=topic,
                    output_path=slide_file,
                )
                pct = 55 + int((idx / len(script.scenes)) * 15)
                await self._emit(
                    task_id=task_id,
                    topic=topic,
                    stage=TaskStage.SCENE_RENDERING,
                    progress_percent=pct,
                    message=f"Rendered slide graphic for scene {idx}/{len(script.scenes)}",
                )

            # ---------------------------------------------------------
            # Stage 4: FFmpeg Video Compositing & Encoding
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.FFMPEG_COMPOSITION,
                progress_percent=75,
                message="Encoding final 1080p video with subtitles, audio sync, and faststart streaming...",
            )
            final_mp4 = temp_dir / "final_course.mp4"
            rendered_video, poster_image = await ffmpeg_composer.compose_video(
                scenes=script.scenes,
                temp_dir=temp_dir,
                output_mp4=final_mp4,
                resolution=resolution,
            )

            # ---------------------------------------------------------
            # Stage 5: Artifact Storage & Delivery
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.UPLOAD_AND_STORAGE,
                progress_percent=92,
                message="Persisting video and thumbnail artifacts to storage...",
            )
            video_url = await storage_manager.save_artifact(task_id, rendered_video, "course_video.mp4")
            thumb_url = await storage_manager.save_artifact(task_id, poster_image, "poster.jpg")

            # ---------------------------------------------------------
            # Stage 6: Completion
            # ---------------------------------------------------------
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.COMPLETED,
                progress_percent=100,
                message="Course video generation completed successfully!",
                video_url=video_url,
                thumbnail_url=thumb_url,
            )
            logger.info("Pipeline completed successfully for task '%s'. Output URL: %s", task_id, video_url)

        except Exception as e:
            logger.exception("Pipeline failed for task '%s': %s", task_id, e)
            await self._emit(
                task_id=task_id,
                topic=topic,
                stage=TaskStage.FAILED,
                progress_percent=0,
                message=f"Pipeline error: {str(e)}",
                error=str(e),
            )
        finally:
            # Clean up intermediate scratch files
            storage_manager.clean_temp_dir(temp_dir)

    async def _emit(
        self,
        task_id: str,
        topic: str,
        stage: TaskStage,
        progress_percent: int,
        message: str,
        video_url: str | None = None,
        thumbnail_url: str | None = None,
        error: str | None = None,
    ):
        """Helper to broadcast pipeline state update to all SSE & WebSocket clients."""
        progress = PipelineProgress(
            task_id=task_id,
            topic=topic,
            stage=stage,
            progress_percent=progress_percent,
            message=message,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            error=error,
        )
        await event_bus.publish(progress)


pipeline_orchestrator = PipelineOrchestrator()
