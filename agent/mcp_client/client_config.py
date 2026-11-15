from pathlib import Path
from pydantic import BaseModel, Field


class McpClientConfig(BaseModel):
  bot_name: str = Field(description="The name of the bot in game")
  game_host: str = Field(description="The host of the Minecraft server")
  game_port: int = Field(description="The port of the Minecraft server")
  game_version: str = Field(description="The version of the Minecraft server")
  viewer_port: int = Field(description="The port of the Minecraft viewer")
  inventory_viewer_port: int = Field(default=4000, description="The port of the Minecraft inventory viewer")
  debug: bool = Field(description="Enable verbose logging in the mcp server")
  server_entry: Path = Field(description="The location of the file to run the mcp servers")
