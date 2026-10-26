"""LLM-driven script and storyboard generator requiring real API credentials."""

import json
import logging
from app.config import settings
from app.models.schemas import CourseScript, ScriptScene

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Produces structured educational scripts, scene breakdowns, and voiceover text via real LLM API."""

    async def generate(self, topic: str, target_scenes: int = 3) -> CourseScript:
        """Calls the configured LLM provider to generate a structured course script."""
        logger.info("Requesting LLM script generation for topic: '%s' (%d scenes)", topic, target_scenes)

        if settings.LLM_PROVIDER == "openai":
            return await self._generate_with_openai(topic, target_scenes)
        elif settings.LLM_PROVIDER == "gemini":
            return await self._generate_with_gemini(topic, target_scenes)
        else:
            raise ValueError(
                f"Unsupported LLM provider '{settings.LLM_PROVIDER}'. Choose 'openai' or 'gemini'."
            )

    async def _generate_with_openai(self, topic: str, target_scenes: int) -> CourseScript:
        """Generates storyboard using OpenAI Structured Outputs."""
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. An LLM API key is strictly required to generate video scripts."
            )

        from openai import AsyncOpenAI

        kwargs = {"api_key": settings.OPENAI_API_KEY}
        if settings.LLM_BASE_URL:
            kwargs["base_url"] = settings.LLM_BASE_URL

        client = AsyncOpenAI(**kwargs)
        prompt = self._build_prompt(topic, target_scenes)

        completion = await client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical educator and video producer. "
                        "Produce an engaging, concise storyboard tailored strictly to the user's requested topic."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format=CourseScript,
        )

        parsed = completion.choices[0].message.parsed
        if not parsed:
            raise RuntimeError("OpenAI returned empty response for script generation.")
        return parsed

    async def _generate_with_gemini(self, topic: str, target_scenes: int) -> CourseScript:
        """Generates storyboard using Google Gemini API."""
        api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. An LLM API key is strictly required to generate video scripts."
            )

        from openai import AsyncOpenAI

        # Use Gemini's official OpenAI-compatible endpoint
        client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        prompt = self._build_prompt(topic, target_scenes)

        response = await client.chat.completions.create(
            model=settings.GEMINI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert educator and video producer. "
                        "Return ONLY valid JSON matching this schema:\n"
                        "{\n"
                        '  "topic": string,\n'
                        '  "headline": string,\n'
                        '  "overview": string,\n'
                        '  "scenes": [\n'
                        "    {\n"
                        '      "scene_number": int (1-indexed),\n'
                        '      "title": string,\n'
                        '      "narration": string (~25-40 words natural voiceover),\n'
                        '      "bullet_points": [string, string, string],\n'
                        '      "key_concept": string,\n'
                        '      "code_or_formula": string or null\n'
                        "    }\n"
                        "  ]\n"
                        "}"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        data = json.loads(content)
        return CourseScript.model_validate(data)

    def _build_prompt(self, topic: str, target_scenes: int) -> str:
        """Builds strict instruction prompt for LLM generation."""
        return f"""
Create a high-quality educational storyboard explaining: "{topic}".
It must have exactly {target_scenes} sequential scenes covering:
1. Scene 1: Fundamental definition, context, and why it matters.
2. Middle Scene(s): Underlying mechanisms, properties, structure, or working principles.
3. Final Scene: Real-world significance, applications, or summary takeaways.

Requirements:
- Narration: Natural, spoken voiceover text (approx 25-45 words per scene).
- Title: Clear slide title (max 6 words).
- Bullet Points: 3 distinct, informative points explaining the concept.
- Key Concept: One focal takeaway term or formula for the slide badge.
- Code or Formula: Relevant scientific formula, chemical reaction, code snippet, or structured diagram text relevant to the topic. If none applies, provide a concise summary axiom.
"""


script_generator = ScriptGenerator()
