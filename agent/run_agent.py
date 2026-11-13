"""Public agent entry point used by acceptance and evaluation scripts."""

from agent.main import clear_all_sessions, clear_session, handle

__all__ = ["handle", "clear_session", "clear_all_sessions"]
