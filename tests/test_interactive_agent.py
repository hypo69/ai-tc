# -*- coding: utf-8 -*-
# =============================================================================
# Process Name: Test Interactive Agent Session
# =============================================================================
# Description:
#   Тестирование стейт-машины сессий интерактивного агента сценариев.
#
# File: test_interactive_agent.py
# Updated: 2026-10-13 15:37:00
# Author: hypo69
# =============================================================================

import asyncio
import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from apps.windows.api.routers import router_interactive_agent as backend_mod
except ImportError:
    backend_mod = importlib.import_module("roadmap.patches.07_interactive_scenario_agent_backend")


class TestInteractiveAgentSession(unittest.TestCase):
    """Тестирование переходов состояний сессии диалогового агента."""

    def test_session_state_machine(self):
        """Проверка инициализации сессии, паузы на ввод и продолжения выполнения."""
        SESSION_STORE = backend_mod.SESSION_STORE
        start_interactive_session = backend_mod.start_interactive_session
        user_reply = backend_mod.user_reply
        StartAgentRequest = backend_mod.StartAgentRequest
        UserReplyRequest = backend_mod.UserReplyRequest

        async def run_test():
            req = StartAgentRequest(user_prompt="Сделай ссылку на папку Public Docs")
            session = await start_interactive_session(req)

            self.assertEqual(session.status, "AWAITING_USER_INPUT")
            self.assertEqual(session.steps[1].step_id, "step_1b_ask_folder")

            # Отвечаем на запрос пути
            reply_req = UserReplyRequest(user_input="C:\\PublicDocs")
            updated_session = await user_reply(session.session_id, reply_req)

            self.assertIn("C:\\PublicDocs", updated_session.context_vars["step_1b_ask_folder"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()

