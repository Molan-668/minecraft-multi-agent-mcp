from __future__ import annotations

import asyncio
import json
import logging
from contextlib import AsyncExitStack

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.session import RequestResponder
from mcp.types import Resource, ReadResourceResult, Tool, CallToolResult

from mcp_client.client_config import McpClientConfig
from model.message import Message

logger = logging.getLogger(__name__)

_SHUTDOWN = object()


class McpClient:
  INCOMING_MESSAGES_URI = "minecraft://incoming-messages"

  def __init__(self, config: McpClientConfig):
    self.config = config
    if not self.config.server_entry.is_file():
      raise FileNotFoundError(
        f"Missing file {self.config.server_entry} — run: cd mcp && npm run build")
    self._session: ClientSession | None = None
    self._session_stack: AsyncExitStack = AsyncExitStack()
    self._new_messages_notification: asyncio.Queue[object] = asyncio.Queue()

  async def start_session(self) -> None:
    server_params = StdioServerParameters(
      command="node",
      args=[str(self.config.server_entry), *self._construct_args()],
      cwd=str(self.config.server_entry.parent),
      env={"NODE_OPTIONS": "--max-old-space-size=4096"},
    )
    logger.info(
      f"[MCP] Starting server: {server_params.command} {server_params.args}")
    read, write = await self._session_stack.enter_async_context(
      stdio_client(server_params)
    )
    session = await self._session_stack.enter_async_context(
      ClientSession(read, write, message_handler=self._message_handler)
    )
    init = await session.initialize()
    logger.info(
      f"[MCP] Connected to {init.serverInfo.name} v{init.serverInfo.version}")
    self._session = session

  def _construct_args(self) -> list[str]:
    return [
      "--botName", self.config.bot_name,
      "--gameHost", self.config.game_host,
      "--gamePort", str(self.config.game_port),
      "--gameVersion", self.config.game_version,
      "--viewerPort", str(self.config.viewer_port),
      "--inventoryViewerPort", str(getattr(self.config, 'inventory_viewer_port', 4000)),
      "--debug", "true" if self.config.debug else "false",
    ]

  async def stop_session(self) -> None:
    self._session = None
    await self._session_stack.aclose()
    logger.info("[MCP] Disconnected from server")

  @property
  def is_session_active(self) -> bool:
    return self._session is not None

  @property
  def session(self) -> ClientSession:
    if self._session is None:
      raise RuntimeError("MCP session not started")
    return self._session

  async def _message_handler(self, message: RequestResponder[types.ServerRequest, types.ClientResult] | types.ServerNotification | Exception) -> None:
    if isinstance(message, Exception):
      logger.error(f"[MCP] Server error: {message}")
      return
    if not isinstance(message, types.ServerNotification):
      return
    root = message.root
    if not isinstance(root, types.ResourceUpdatedNotification):
      return
    if str(root.params.uri) != self.INCOMING_MESSAGES_URI:
      return
    self._new_messages_notification.put_nowait(None)

  async def list_resources(self) -> list[Resource]:
    res = await self.session.list_resources()
    return res.resources

  async def list_tools(self) -> list[Tool]:
    res = await self.session.list_tools()
    return res.tools

  async def call_tool(self, tool_name: str, tool_input: dict) -> CallToolResult:
    res = await self.session.call_tool(tool_name, tool_input)
    return res

  async def subscribe_resource(self, uri: str) -> None:
    await self.session.subscribe_resource(uri)
    logger.info(f"[MCP] Subscribed to resource: {uri}")

  async def read_resource(self, uri: str) -> ReadResourceResult:
    res = await self.session.read_resource(uri)
    logger.debug(f"[MCP] Read resource: {uri}")
    return res

  def signal_shutdown(self) -> None:
    self._new_messages_notification.put_nowait(_SHUTDOWN)

  async def wait_for_incoming_messages(self) -> bool:
    item = await self._new_messages_notification.get()
    return item is not _SHUTDOWN

  async def fetch_incoming_messages(self) -> list[Message]:
    res = await self.read_resource(self.INCOMING_MESSAGES_URI)
    if not res.contents:
      return []
    text = res.contents[0].text
    if not text:
      return []
    parsed = json.loads(text)
    if not isinstance(parsed, list):
      raise ValueError(f"Expected JSON array, got {type(parsed).__name__}")
    messages = [Message.model_validate(message) for message in parsed]
    return messages
