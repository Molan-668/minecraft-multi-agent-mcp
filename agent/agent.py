import asyncio
import contextlib
import json
import logging
import subprocess
import time
from config import AgentConfig
from llm import LLMClient
from mas import parse_mas_messages
from mcp_client import McpClient
from memory import MemoryManager
from model.message import Message

logger = logging.getLogger(__name__)

_MESSAGE_BOX_SHUTDOWN_TIMEOUT = 2.0


class Agent:
    COGNITION_REST_PERIOD_MS = 500

    def __init__(self, config: AgentConfig):
        self.config = config
        self._mcp_client: McpClient | None = None
        self.message_box: list[Message] = []
        self._update_message_box_task: asyncio.Task[None] | None = None

        self.llm: LLMClient | None = None
        self.memory: MemoryManager | None = None
        self.current_task: str = ""
        self.last_tool_name: str = ""
        self.last_tool_args: dict = {}
        self.last_observation: str = ""
        self.task_done: bool = False
        self._processed_message_count: int = 0
        self._max_iterations: int = 200
        self._iteration_count: int = 0
        self._key_observations: list[str] = []
        self._trajectory: list[dict] = []
        self._done_agents: set[str] = set()
        self._my_done_broadcasted: bool = False
        self._team_size: int = 1
        self._team_timeout: float = 600.0
        self._start_time: float = 0.0
        self._stuck_counter: dict[str, int] = {}
        self._stuck_warning: str = ""

    async def start(self) -> None:
        if self._mcp_client:
            return
        self._mcp_client = McpClient(self.config.mcp_client_config)
        await self._mcp_client.start_session()
        resources = await self._mcp_client.list_resources()
        if not any(str(resource.uri) == McpClient.INCOMING_MESSAGES_URI for resource in resources):
            raise ValueError("Incoming messages resource not found in MCP server")
        await self._mcp_client.subscribe_resource(McpClient.INCOMING_MESSAGES_URI)
        await self._drain_incoming_messages()
        self._update_message_box_task = asyncio.create_task(
            self._handle_update_message_box())

    async def _drain_incoming_messages(self) -> None:
        messages = await self._mcp_client.fetch_incoming_messages()
        self.message_box.extend(messages)
        for message in messages:
            logger.info(
                f"[{message.type.upper()}] {message.sender}: {message.content}")

    def _is_mcp_client_gone(self) -> bool:
        client = self._mcp_client
        if client is None:
            return True
        return not client.is_session_active

    async def _handle_update_message_box(self) -> None:
        while True:
            if self._is_mcp_client_gone():
                break
            try:
                if not await self._mcp_client.wait_for_incoming_messages():
                    break
                await self._drain_incoming_messages()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Failed to update message box")
                if self._is_mcp_client_gone():
                    logger.warning("MCP client gone, stopping message box updater")
                    break

    async def stop(self) -> None:
        task = self._update_message_box_task
        client = self._mcp_client
        if client:
            client.signal_shutdown()
        if task:
            try:
                await asyncio.wait_for(task, timeout=_MESSAGE_BOX_SHUTDOWN_TIMEOUT)
            except asyncio.TimeoutError:
                logger.debug("Message box updater did not exit in time, cancelling...")
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._update_message_box_task = None
        if client:
            await client.stop_session()
            self._mcp_client = None

    async def run(self) -> None:
        await self.start()
        self._start_time = time.time()
        try:
            await self._pre_loop()
            while not self.task_done and self._iteration_count < self._max_iterations:
                await self._loop_once()
                self._iteration_count += 1
                await asyncio.sleep(self.COGNITION_REST_PERIOD_MS / 1000)
            if self._iteration_count >= self._max_iterations:
                logger.warning(f"Reached max iterations ({self._max_iterations}), stopping")
        finally:
            elapsed = time.time() - self._start_time
            logger.info(f"METRICS: task='{self.current_task}', iterations={self._iteration_count}, success={self.task_done}, time={elapsed:.1f}s")
            await self._post_loop()
            await self.stop()

    async def _pre_loop(self) -> None:
        tools = await self._mcp_client.list_tools()
        tool_descriptions = []
        for tool in tools:
            schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
            props = schema.get("properties", {}) if isinstance(schema, dict) else {}
            desc = f"- **{tool.name}**: {tool.description or '(no description)'}"
            if props:
                desc += "\n  Parameters:"
                for pname, pinfo in props.items():
                    ptype = pinfo.get("type", "any") if isinstance(pinfo, dict) else "any"
                    pdesc = pinfo.get("description", "") if isinstance(pinfo, dict) else ""
                    desc += f"\n    - {pname} ({ptype}): {pdesc}"
            tool_descriptions.append(desc)

        tools_text = "\n".join(tool_descriptions)
        logger.info(f"Loaded {len(tools)} tools")

        self.llm = LLMClient(
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_base_url,
            model=self.config.llm_model,
        )
        self.llm.set_tools_description(tools_text)

        self.memory = MemoryManager()
        memory_context = self.memory.get_relevant_memories(self.current_task)
        if memory_context:
            self.llm.inject_memory(memory_context)
            logger.info(f"Injected memory context ({len(memory_context)} chars)")

        self.current_task = self.config.task
        self._team_size = self.config.team_size
        self._team_timeout = self.config.team_timeout
        logger.info(f"Agent '{self.config.name}' starting with task: {self.current_task} (team of {self._team_size})")

        if self.config.clear_inventory:
            logger.info(f"Clearing inventory via RCON...")
            try:
                subprocess.run(
                    ["docker", "compose", "exec", "mc", "rcon-cli", f"clear {self.config.name}"],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(self.config.mcp_client_config.server_entry.parent.parent.parent / "sandbox"),
                )
                await asyncio.sleep(1.0)
            except Exception as e:
                logger.warning(f"RCON clear failed: {e}")

        if self._team_size > 1:
            await self._mcp_client.call_tool("chat", {"message": f"[REGISTER] {self.config.name}"})
            await asyncio.sleep(0.5)
            logger.info(f"Registered with team (size={self._team_size})")

        given_items: list[str] = []
        for cmd in self.config.initial_commands:
            parts = cmd.split()
            if len(parts) >= 3:
                item_name = parts[2]
                count = parts[3] if len(parts) > 3 else '1'
                given_items.append(f"{item_name} x{count}")
                rcon_cmd = f"give {self.config.name} {item_name} {count}"
                logger.info(f"Giving item via RCON: {rcon_cmd}")
                try:
                    result = subprocess.run(
                        ["docker", "compose", "exec", "mc", "rcon-cli", rcon_cmd],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(self.config.mcp_client_config.server_entry.parent.parent.parent / "sandbox"),
                    )
                    logger.info(f"RCON result: {result.stdout.strip() or result.stderr.strip()}")
                except Exception as e:
                    logger.warning(f"RCON failed: {e}")

        resp = await self._mcp_client.call_tool("check_inventory", {})
        if resp.content and resp.content[0].text:
            inv_text = str(resp.content[0].text)
            self.last_observation = "Initial inventory:\n" + inv_text
        else:
            self.last_observation = "Inventory is empty"

        if given_items:
            self.last_observation += "\n\nCRITICAL: You have ALREADY been given these items: " + ", ".join(given_items) + ". These items ARE in your inventory right now even if they don't appear above (the inventory display may be incomplete). You DO NOT need to chase animals or mine for these items. Just use them directly."

        resp = await self._mcp_client.call_tool("position", {})
        if resp.content and resp.content[0].text:
            self.last_observation += "\n\nCurrent position: " + str(resp.content[0].text)

        logger.info(f"Pre-loop complete, ready for task")

    async def _loop_once(self) -> None:
        new_messages = self.message_box[self._processed_message_count:]
        self._processed_message_count = len(self.message_box)

        chat_lines = []
        mas_lines = []
        if new_messages:
            for msg in new_messages:
                line = f"[{msg.type.upper()}] {msg.sender}: {msg.content}"
                chat_lines.append(line)
                content = msg.content if hasattr(msg, "content") else ""
                sender = msg.sender if hasattr(msg, "sender") else ""
                # Track team registrations and completions
                if content.startswith("[REGISTER]") and sender != self.config.name:
                    self._done_agents.add(sender)
                    logger.info(f"Teammate registered: {sender}")
                if content.startswith("[DONE]") and sender != self.config.name:
                    self._done_agents.add(sender)
                    logger.info(f"Teammate done: {sender} ({len(self._done_agents)+1}/{self._team_size})")
            mas_msgs = parse_mas_messages(new_messages)
            for m in mas_msgs:
                mas_lines.append(f"**Agent {m.sender}**: {m.msg_type} {m.content}")

        chat_text = "(no new messages)"
        if chat_lines:
            chat_text = "\n".join(chat_lines)

        mas_text = ""
        if mas_lines:
            mas_text = "## Agent Messages\n" + "\n".join(mas_lines)

        full_context = chat_text
        if mas_text:
            full_context += "\n\n" + mas_text

        # Team timeout check
        elapsed = time.time() - self._start_time
        if self._team_size > 1 and elapsed > self._team_timeout:
            logger.warning(f"Team timeout ({self._team_timeout}s) reached, forcing exit")
            self.task_done = True
            return

        # All teammates done + self done → exit
        if self._team_size > 1 and self._my_done_broadcasted and len(self._done_agents) + 1 >= self._team_size:
            logger.info(f"All {self._team_size} teammates done, exiting together")
            self.task_done = True
            return

        # If my task is done but teammates still working, just wait
        if self._my_done_broadcasted:
            remaining = self._team_size - len(self._done_agents) - 1
            logger.debug(f"Waiting for {remaining} more teammate(s)...")
            await asyncio.sleep(2.0)
            return

        last_action_str = f"Tool: {self.last_tool_name}\nArgs: {json.dumps(self.last_tool_args)}" if self.last_tool_name else "(none)"
        last_obs_str = (self.last_observation or "(none)")
        if self._stuck_warning:
            last_obs_str = self._stuck_warning + "\n\n" + last_obs_str

        last_obs_str = (self.last_observation or "(none)")
        if self._stuck_warning:
            last_obs_str = self._stuck_warning + "\n\n" + last_obs_str

        result = await self.llm.think(
            task=self.current_task,
            chat_messages=full_context,
            last_action=last_action_str,
            last_observation=last_obs_str,
        )

        tool_name = result.get("tool_name", "")
        tool_args = result.get("tool_args", {})
        reasoning = result.get("reasoning", "")

        logger.info(f"[ITER {self._iteration_count}] Reasoning: {reasoning}")
        logger.info(f"[ITER {self._iteration_count}] Action: {tool_name}({json.dumps(tool_args)})")

        if tool_name == "task_complete":
            message = tool_args.get("message", "Task completed")
            logger.info(f"My task done: {message}")
            if self._is_mcp_client_gone():
                logger.warning("MCP client gone, cannot send completion message")
            else:
                try:
                    await self._mcp_client.call_tool("chat", {"message": f"[DONE] {message}"})
                except Exception:
                    pass
            self._my_done_broadcasted = True
            if self._team_size <= 1:
                self.task_done = True
            else:
                logger.info(f"Broadcast [DONE], waiting for {self._team_size - 1} teammate(s)...")
                self.last_observation = "My task is done. Waiting for teammates to finish."
            return

        try:
            response = await asyncio.wait_for(
                self._mcp_client.call_tool(tool_name, tool_args),
                timeout=45.0
            )
            obs_parts = []
            if response.content:
                for c in response.content:
                    if hasattr(c, 'text') and c.text:
                        obs_parts.append(str(c.text))
            self.last_observation = "\n".join(obs_parts) if obs_parts else "(tool executed successfully, no output)"
        except asyncio.TimeoutError:
            self.last_observation = "Tool TIMEOUT — took too long. Try a different approach (smaller max_distance, different block, or skip this step)."
            logger.warning(f"Tool timeout: {tool_name}")
        except Exception as e:
            self.last_observation = f"Error: {e}"
            logger.error(f"Tool call failed: {tool_name} -> {e}")
            if self._is_mcp_client_gone():
                logger.warning("MCP client gone, stopping")
                self.task_done = True
                return

        self.last_tool_name = tool_name
        self.last_tool_args = tool_args

        # Detect repeat-fail loops (same tool+args failing repeatedly)
        action_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}" if tool_name else ""
        is_failure = ("Error" in self.last_observation[:20] or
                      "Failed" in self.last_observation[:20] or
                      "wedged" in self.last_observation.lower() or
                      "cannot place" in self.last_observation.lower())
        if tool_name and is_failure:
            self._stuck_counter[action_key] = self._stuck_counter.get(action_key, 0) + 1
        elif tool_name and ("Reached" in self.last_observation or "Collected" in self.last_observation or "Placed" in self.last_observation):
            self._stuck_counter.pop(action_key, None)

        stuck_keys = [k for k, v in self._stuck_counter.items() if v >= 3]
        if stuck_keys:
            self._stuck_warning = f"WARNING: You have been stuck repeating these failing actions: {', '.join(stuck_keys)}. Stop trying them! Try a completely different approach: move somewhere else, use range>0, or choose a different block nearby."
            logger.warning(f"Stuck detected: {stuck_keys}")
        else:
            self._stuck_warning = ""

        logger.info(f"[ITER {self._iteration_count}] Observation: {self.last_observation[:300]}")

        if self.memory:
            self.memory.learn_from_iteration(tool_name, self.last_observation, reasoning)
            self._trajectory.append({
                "reasoning": reasoning,
                "tool_name": tool_name,
                "tool_args": dict(tool_args),
                "observation": self.last_observation[:200],
            })

    async def _post_loop(self) -> None:
        if self.memory:
            self.memory.record_task_trajectory(
                task=self.current_task,
                success=self.task_done,
                iterations=self._iteration_count,
                trajectory=self._trajectory,
            )
        if self.task_done:
            logger.info(f"Agent '{self.config.name}' completed task successfully")
        else:
            logger.warning(f"Agent '{self.config.name}' stopped without completing task")
        self.llm = None
        self.memory = None
