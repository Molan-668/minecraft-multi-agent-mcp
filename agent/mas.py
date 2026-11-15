"""
Multi-agent collaboration protocol handler.
Parses agent-to-agent messages and extracts cooperation intents.
"""

import logging

logger = logging.getLogger(__name__)

MSG_TASK = "[TASK]"
MSG_OFFER = "[OFFER]"
MSG_REQUEST = "[REQUEST]"
MSG_DROP = "[DROP]"
MSG_DONE = "[DONE]"
MSG_HAVE = "[HAVE]"


class MasMessage:
    def __init__(self, sender: str, msg_type: str, content: str = "", raw: str = ""):
        self.sender = sender
        self.msg_type = msg_type
        self.content = content
        self.raw = raw

    def __repr__(self):
        return f"MasMessage(from={self.sender}, type={self.msg_type}, content={self.content[:50]})"


def parse_mas_messages(chat_messages: list) -> list[MasMessage]:
    """Extract MAS protocol messages from chat."""
    results = []
    for msg in chat_messages:
        raw = msg.content if hasattr(msg, "content") else str(msg)
        sender = msg.sender if hasattr(msg, "sender") else ""
        if not isinstance(raw, str):
            continue
        for prefix in [MSG_TASK, MSG_OFFER, MSG_REQUEST, MSG_DROP, MSG_DONE, MSG_HAVE]:
            if raw.startswith(prefix):
                results.append(MasMessage(sender, prefix, raw[len(prefix):].strip(), raw))
                break
    return results


def format_task(task_name: str, description: str = "") -> str:
    return f"{MSG_TASK} {task_name}: {description}"

def format_offer(item_list: str) -> str:
    return f"{MSG_OFFER} {item_list}"

def format_request(item_name: str, count: int = 1) -> str:
    return f"{MSG_REQUEST} {item_name} x{count}"

def format_drop(item_name: str, count: int = 1) -> str:
    return f"{MSG_DROP} {item_name} x{count}"

def format_done(task_name: str) -> str:
    return f"{MSG_DONE} {task_name}"

def format_have(item_list: str) -> str:
    return f"{MSG_HAVE} {item_list}"
