"""Unit tests for pipeline components (LLM script validation, slide rendering, TTS validation)."""

from pathlib import Path
import pytest
from PIL import Image

from app.models.schemas import ScriptScene
from app.pipeline.script_generator import script_generator
from app.pipeline.visual_generator import visual_generator
from app.pipeline.tts_synthesizer import tts_synthesizer


@pytest.mark.asyncio
async def test_script_generator_requires_api_key(monkeypatch):
    """Verify script generator raises ValueError when API key is missing."""
    monkeypatch.setattr("app.config.settings.OPENAI_API_KEY", None)
    monkeypatch.setattr("app.config.settings.GEMINI_API_KEY", None)
    monkeypatch.setattr("app.config.settings.LLM_PROVIDER", "openai")

    with pytest.raises(ValueError, match="OPENAI_API_KEY is not set"):
        await script_generator.generate(topic="Solar System", target_scenes=3)


def test_visual_generator_slide_rendering(tmp_path: Path):
    """Verify Pillow generates a valid 1920x1080 slide image."""
    scene = ScriptScene(
        scene_number=1,
        title="The Solar System",
        narration="The solar system consists of the Sun and celestial bodies bound by gravity.",
        bullet_points=["Eight recognized planets", "Asteroid and Kuiper belts", "Heliocentric model"],
        key_concept="Gravitational Equilibrium",
        code_or_formula="F = G * (m1 * m2) / r^2",
    )
    output_png = tmp_path / "test_slide.png"
    result_path = visual_generator.render_scene_slide(
        scene=scene,
        total_scenes=3,
        topic="Solar System",
        output_path=output_png,
    )

    assert result_path.exists()
    with Image.open(result_path) as img:
        assert img.size == (1920, 1080)
        assert img.format == "PNG"


@pytest.mark.asyncio
async def test_tts_synthesizer_rejects_empty_narration(tmp_path: Path):
    """Verify TTS synthesizer raises ValueError on empty narration text."""
    scene = ScriptScene(
        scene_number=1,
        title="Empty Scene",
        narration="",
        bullet_points=[],
    )
    output_mp3 = tmp_path / "empty.mp3"
    with pytest.raises(ValueError, match="empty narration text"):
        await tts_synthesizer.synthesize_scene(scene, output_mp3)
