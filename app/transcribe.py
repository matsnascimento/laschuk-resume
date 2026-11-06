"""Pluggable transcription: OpenAI Whisper API or local faster-whisper."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
from typing import Protocol

import httpx

from .config import Settings
from .parse import mime_extension

log = logging.getLogger("laschuk_resume.transcribe")

OPENAI_MAX_BYTES = 25 * 1024 * 1024


class TranscriptionError(RuntimeError):
    pass


class Transcriber(Protocol):
    name: str

    async def transcribe(self, audio: bytes, mimetype: str) -> str: ...


class OpenAITranscriber:
    name = "openai"

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.s = settings
        self.http = client

    async def transcribe(self, audio: bytes, mimetype: str) -> str:
        if len(audio) > OPENAI_MAX_BYTES:
            raise TranscriptionError(f"audio is {len(audio)} bytes; OpenAI limit is 25 MB")
        ext = mime_extension(mimetype)
        data = {"model": self.s.openai_transcribe_model, "response_format": "json"}
        if self.s.transcribe_language:
            data["language"] = self.s.transcribe_language
        try:
            resp = await self.http.post(
                f"{self.s.openai_base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.s.openai_api_key}"},
                data=data,
                files={"file": (f"audio.{ext}", audio, mimetype.split(";")[0] or "audio/ogg")},
            )
        except httpx.HTTPError as exc:
            raise TranscriptionError(f"OpenAI transcription request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise TranscriptionError(f"OpenAI transcription HTTP {resp.status_code}: {resp.text[:300]}")
        return str(resp.json().get("text") or "").strip()


class LocalWhisperTranscriber:
    name = "local"
    _model = None
    _model_lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.s = settings
        try:
            import faster_whisper  # noqa: F401
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed (pip install -r requirements-local.txt)"
            ) from exc

    def _get_model(self):
        with self._model_lock:
            if LocalWhisperTranscriber._model is None:
                from faster_whisper import WhisperModel

                log.info("loading faster-whisper model %s (%s/%s)", self.s.local_whisper_model,
                         self.s.local_whisper_device, self.s.local_whisper_compute_type)
                LocalWhisperTranscriber._model = WhisperModel(
                    self.s.local_whisper_model,
                    device=self.s.local_whisper_device,
                    compute_type=self.s.local_whisper_compute_type,
                )
            return LocalWhisperTranscriber._model

    def _run(self, audio: bytes, mimetype: str) -> str:
        fd, path = tempfile.mkstemp(suffix="." + mime_extension(mimetype))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(audio)
            segments, _info = self._get_model().transcribe(
                path, language=self.s.transcribe_language or None, vad_filter=True
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    async def transcribe(self, audio: bytes, mimetype: str) -> str:
        try:
            return await asyncio.to_thread(self._run, audio, mimetype)
        except TranscriptionError:
            raise
        except Exception as exc:  # decoding / model errors
            raise TranscriptionError(f"local transcription failed: {exc}") from exc


def build_transcriber(settings: Settings, client: httpx.AsyncClient) -> Transcriber:
    mode = settings.transcriber
    if mode == "openai" or (mode == "auto" and settings.openai_api_key):
        return OpenAITranscriber(settings, client)
    if mode in {"local", "auto"}:
        return LocalWhisperTranscriber(settings)
    raise TranscriptionError(f"unknown TRANSCRIBER {mode!r}")
