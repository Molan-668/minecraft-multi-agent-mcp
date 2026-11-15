import argparse
import asyncio
import logging
from pathlib import Path
from config import AgentConfig
from mcp_client import McpClientConfig
from agent import Agent


logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parent
_DEFAULT_MCP_ENTRY = (_AGENT_DIR / ".." / "mcp" / "dist" / "index.js").resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Agent to interact with a Minecraft environment"
    )
    parser.add_argument("--name", type=str, default="Steve",
                        help="Name of the agent")
    parser.add_argument("--game-host", type=str,
                        default="127.0.0.1", help="Host of the Minecraft server")
    parser.add_argument("--game-port", type=int, default=25565,
                        help="Port of the Minecraft server")
    parser.add_argument("--game-version", type=str,
                        default="1.21.4", help="Version of the Minecraft server")
    parser.add_argument("--viewer-port", type=int, default=3000,
                        help="Port of the Minecraft viewer")
    parser.add_argument("--inventory-viewer-port", type=int, default=4000,
                        help="Port of the Minecraft inventory viewer")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument("--llm-api-key", type=str,
                        default="",
                        help="API key for the LLM service")
    parser.add_argument("--llm-base-url", type=str,
                        default="https://api.deepseek.com", help="Base URL for the LLM API")
    parser.add_argument("--llm-model", type=str,
                        default="deepseek-chat", help="LLM model name")

    parser.add_argument("--task", type=str, default="",
                        help="Task for the agent to accomplish")
    parser.add_argument("--give", type=str, action="append", default=[],
                        help="Initial /give command (can be repeated, e.g.: --give 'raw_iron 1')")
    parser.add_argument("--team-size", type=int, default=1,
                        help="Number of agents in the team (for coordinated exit)")
    parser.add_argument("--team-timeout", type=int, default=600,
                        help="Max seconds before forcing team exit")
    parser.add_argument("--clear-inventory", action="store_true",
                        help="Clear bot inventory before starting (via RCON)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    initial_commands = [f"/give @s {item}" for item in args.give]

    config = AgentConfig(
        name=args.name,
        mcp_client_config=McpClientConfig(
            bot_name=args.name,
            game_host=args.game_host,
            game_port=args.game_port,
            game_version=args.game_version,
            viewer_port=args.viewer_port,
            inventory_viewer_port=args.inventory_viewer_port,
            debug=args.debug,
            server_entry=_DEFAULT_MCP_ENTRY,
        ),
        llm_api_key=args.llm_api_key,
        llm_base_url=args.llm_base_url,
        llm_model=args.llm_model,
        task=args.task,
        initial_commands=initial_commands,
        team_size=args.team_size,
        team_timeout=args.team_timeout,
        clear_inventory=args.clear_inventory,
    )
    agent = Agent(config)
    await agent.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
