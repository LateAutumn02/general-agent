"""Textual widgets for general-agent UI."""

from general_agent.ui.widgets.chat import ChatContainer, PanelMeta
from general_agent.ui.widgets.editor import PromptInput, EditorSubmitRequested
from general_agent.ui.widgets.messages import CompactionStatusChanged, SystemNoticeDisplay, ToolResultDisplay
from general_agent.ui.widgets.status_bar import StatusBar

__all__ = [
    "ChatContainer",
    "CompactionStatusChanged",
    "EditorSubmitRequested",
    "PanelMeta",
    "PromptInput",
    "StatusBar",
    "SystemNoticeDisplay",
    "ToolResultDisplay",
]
