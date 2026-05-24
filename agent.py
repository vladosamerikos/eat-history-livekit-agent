"""
LiveKit voice agent for Eat History.

Recibe un job dispatched explícitamente desde el backend (NestJS) con metadata:
    {
      "userId": str,
      "locale": "es" | "en" | "uk",
      "mcpToken": <JWT corto para llamar al MCP>,
      "apiBase":  "https://eat-history.vladys.dev/v1"
    }

- STT: Google Cloud Speech-to-Text (streaming)
- TTS: Google Cloud Text-to-Speech (Neural2/Wavenet)
- LLM: Vertex Gemini 2.5-flash (vía google-genai con vertexai=True)
- Tools: las del MCP server en /v1/mcp (HTTP streamable) usando el mcpToken.

El agente habla en el idioma del usuario (locale) y nunca lo cambia salvo
instrucción explícita.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    WorkerOptions,
    mcp,
    llm,
)
from livekit.plugins import google, silero

import config

logger = logging.getLogger("eat-history-agent")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

AGENT_NAME = "eat-history"


def load_prompts_for_locale(locale: str) -> tuple[str, str, str]:
    supported_locales = ["es", "en", "uk"]
    loc = locale if locale in supported_locales else "es"
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(current_dir, "prompts", f"{loc}.txt")
    
    system_prompt = "Eres el asistente de voz de Eat History. Ayuda al usuario a registrar comidas y peso."
    greeting_prompt = "Genera un saludo inicial amigable."
    greeting_fallback = "Hola, ¿qué has comido hoy?"
    
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Extract greeting fallback
        if "=== GREETING_FALLBACK ===" in content:
            parts_fallback = content.split("=== GREETING_FALLBACK ===")
            greeting_fallback = parts_fallback[1].strip()
            content = parts_fallback[0]
            
        # Extract system and greeting prompts
        if "=== GREETING_PROMPT ===" in content:
            parts_greeting = content.split("=== GREETING_PROMPT ===")
            greeting_prompt = parts_greeting[1].strip()
            system_part = parts_greeting[0].replace("=== SYSTEM_PROMPT ===", "").strip()
            if system_part:
                system_prompt = system_part
        else:
            system_prompt = content.replace("=== SYSTEM_PROMPT ===", "").strip()
    except Exception as e:
        logger.error("Error loading prompts for %s: %s", loc, e)
        
    return system_prompt, greeting_prompt, greeting_fallback


@dataclass
class JobMeta:
    user_id: str
    locale: str
    mcp_token: str
    api_base: str
    photo_url: str = ""

    @classmethod
    def parse(cls, raw: str | None) -> "JobMeta":
        data: dict[str, Any] = json.loads(raw) if raw else {}
        return cls(
            user_id=data.get("userId", "unknown"),
            locale=data.get("locale", "es"),
            mcp_token=data.get("mcpToken", ""),
            api_base=data.get("apiBase", "https://eat-history.vladys.dev/v1"),
            photo_url=data.get("photoUrl", "") or "",
        )


def prewarm(proc: JobProcess) -> None:
    """Preload VAD model so the first request is fast."""
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext) -> None:
    meta = JobMeta.parse(ctx.job.metadata)
    logger.info("job start user=%s locale=%s room=%s", meta.user_id, meta.locale, ctx.room.name)

    await ctx.connect()

    stt_lang = config.STT_LANG.get(meta.locale, "es-ES")
    tts_lang, tts_voice = config.get_tts_voice(meta.locale)

    instructions, greeting_prompt, greeting_fallback = load_prompts_for_locale(meta.locale)

    # Si la sesión se ha abierto con una foto adjunta (p.ej. desde el botón
    # de la cámara), inyectamos una pista al system prompt para que el LLM
    # sepa que puede usar la herramienta `meals_add_from_photo`.
    if meta.photo_url:
        photo_hint = (
            "\n\n[CONTEXTO DE SESIÓN]\n"
            f"El usuario ha adjuntado una foto de su plato: {meta.photo_url}\n"
            "Saluda brevemente y ofrécele analizarla. Si acepta (o si te pide\n"
            "registrar la comida), llama a la tool `meals_add_from_photo` con\n"
            f"`photo_url=\"{meta.photo_url}\"` y el `type` adecuado (breakfast,\n"
            "lunch, snack o dinner) según el contexto u hora actual. Confirma\n"
            "al usuario los items detectados y el total de kcal."
        )
        instructions = instructions + photo_hint
        greeting_prompt = (
            f"{greeting_prompt}\n\nEl usuario acaba de adjuntar una foto de su comida. "
            "Salúdalo y preguntale brevemente si quieres que la analices y la registres."
        )

    @llm.function_tool(
        description="Ends the call/hangs up. Call this when the user says they are done, want to say goodbye, or want to hang up."
    )
    def end_call() -> str:
        logger.info("Ending call per user request")
        asyncio.create_task(ctx.disconnect())
        return "Ending the call. Goodbye!"

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=google.STT(
            languages=[stt_lang],
            model="latest_long",
        ),
        llm=google.LLM(
            model=config.LLM_MODEL,
            vertexai=True,
            project=os.getenv("GOOGLE_VERTEX_PROJECT"),
            location=os.getenv("GOOGLE_VERTEX_LOCATION", "us-central1"),
        ),
        tts=google.TTS(language=tts_lang, voice_name=tts_voice),
        tools=[end_call],
        mcp_servers=[
            mcp.MCPServerHTTP(
                url=f"{meta.api_base}/mcp",
                headers={"Authorization": f"Bearer {meta.mcp_token}"},
                timeout=15,
                client_session_timeout_seconds=30,
            ),
        ],
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=instructions),
        room_input_options=RoomInputOptions(),
    )

    # Generar saludo inicial dinámico y auténtico usando el LLM
    try:
        greeting_ctx = llm.ChatContext()
        greeting_ctx.add_message(role="user", content=greeting_prompt)
        
        stream = session.llm.chat(chat_ctx=greeting_ctx)
        greeting_text = ""
        async for chunk in stream:
            if chunk.delta and chunk.delta.content:
                greeting_text += chunk.delta.content
        greeting_text = greeting_text.strip()
    except Exception as e:
        logger.error("Error generating dynamic greeting: %s", e)
        greeting_text = greeting_fallback

    await session.say(greeting_text, allow_interruptions=True)


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=AGENT_NAME,
        )
    )
