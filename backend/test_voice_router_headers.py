import sys
import types
import unittest
from pathlib import Path


class VoiceRouterHeaderSafetyTests(unittest.TestCase):
    def _import_voice_router_lightweight(self):
        # `voice_router` imports `chat_service` which pulls in heavy ML deps via `ml_service`.
        # Stub `chat_service` out to keep this test fast and offline.
        sys.modules.pop("voice_router", None)
        backend_dir = str(Path(__file__).resolve().parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)

        chat_service_stub = types.ModuleType("chat_service")

        class ChatService:  # noqa: N801 - match imported name
            def __init__(self, user_id: str):
                self.user_id = user_id

            def chat(self, _text: str) -> str:
                return "ok"

        chat_service_stub.ChatService = ChatService
        sys.modules["chat_service"] = chat_service_stub

        import voice_router

        return voice_router

    def test_sanitize_header_value_strips_newlines_and_trailing_space(self) -> None:
        voice_router = self._import_voice_router_lightweight()
        from starlette.responses import Response

        sanitized = voice_router._sanitize_header_value("Hello there!\n", max_len=512)
        self.assertEqual(sanitized, "Hello there!")
        # Starlette encodes headers to latin-1 and h11 validates them; this should not raise.
        Response(content=b"x", headers={"X-Assistant-Reply": sanitized}).raw_headers

    def test_sanitize_header_value_handles_unicode_and_controls(self) -> None:
        voice_router = self._import_voice_router_lightweight()
        from starlette.responses import Response

        sanitized = voice_router._sanitize_header_value("hi\u2028there\u0007 😀", max_len=512)
        self.assertNotIn("\n", sanitized)
        self.assertNotIn("\r", sanitized)
        Response(content=b"x", headers={"X-Assistant-Reply": sanitized}).raw_headers

    def test_sanitize_header_value_truncates(self) -> None:
        voice_router = self._import_voice_router_lightweight()
        from starlette.responses import Response

        long_text = "a" * 10_000
        sanitized = voice_router._sanitize_header_value(long_text, max_len=200)
        self.assertEqual(len(sanitized), 200)
        Response(content=b"x", headers={"X-Assistant-Reply": sanitized}).raw_headers
