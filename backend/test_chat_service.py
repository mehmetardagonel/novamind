import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


class ChatServiceLangChainConfigTests(unittest.TestCase):
    def test_agent_executor_early_stopping_method_is_force(self) -> None:
        os.environ["GEMINI_API_KEY"] = "test-key"

        # `chat_service` imports `ml_service`, which imports heavy ML deps (torch/transformers).
        # Stub it out so the test stays lightweight and doesn't touch temp directories.
        sys.modules.pop("chat_service", None)
        sys.modules["ml_service"] = types.ModuleType("ml_service")
        sys.modules["ml_service"].get_classifier = lambda: None

        import chat_service

        with (
            patch.object(chat_service, "ChatGoogleGenerativeAI", autospec=True) as mock_llm_cls,
            patch.object(chat_service, "create_tool_calling_agent", autospec=True) as mock_create_agent,
            patch.object(chat_service, "AgentExecutor", autospec=True) as mock_agent_executor_cls,
        ):
            mock_llm_cls.return_value = MagicMock(name="llm")
            mock_create_agent.return_value = MagicMock(name="agent")
            mock_agent_executor_cls.return_value = MagicMock(name="executor")

            chat_service.ChatService(user_id="u1")

            _args, kwargs = mock_agent_executor_cls.call_args
            self.assertEqual(kwargs.get("early_stopping_method"), "force")
