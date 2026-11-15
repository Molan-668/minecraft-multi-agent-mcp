from typing import Literal
from pydantic import BaseModel, Field

MessageType = Literal["chat", "whisper"]


class Message(BaseModel):
  """
  A message received by the agent.
  """
  type: MessageType = Field(
    description="Whether this is a private message (whisper) or a public chat message (chat)")
  sender: str = Field(description="Sender of the message")
  content: str = Field(description="Content of the message")
