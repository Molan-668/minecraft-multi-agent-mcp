# Language-model agents in Minecraft

This project connects a Python agent to a Minecraft world through the Model Context Protocol (MCP). A task such as cooking a steak requires the agent to coordinate several game actions, including gathering supplies, crafting equipment, and using a furnace. Team runs add communication between bots.

## How a task reaches the game

The [Python agent](agent/agent.py) communicates with the language model and requests game actions. [Memory](agent/memory.py) maintains agent context, and [mas.py](agent/mas.py) parses team messages. The [TypeScript MCP server](mcp/src/) exposes Mineflayer operations for movement, inventory, crafting, and interactions with blocks and containers.

## Start a local session

1. In [sandbox](sandbox/), copy `.env_example` to `.env`, configure the world, and start the Minecraft server with `docker compose up -d`. See the [server instructions](sandbox/README.md).
2. In [mcp](mcp/), use Node.js 20 or newer and run `npm ci`, then `npm run build`. The Python launcher expects the compiled entry point at `mcp/dist/index.js`.
3. In [agent](agent/), run `uv sync`. Set `LLM_API_KEY` in your local PowerShell session, then start a bot with the command below. Set `--llm-base-url` and `--llm-model` to values supported by your provider if its settings differ from the defaults.

```powershell
uv run python main.py --name Steve --llm-api-key "$env:LLM_API_KEY" --task "Introduce yourself in chat"
```

The [project report](AMAS_Assigment3.pdf) documents the design and experiments. The [agent guide](agent/README.md) and [MCP guide](mcp/README.md) cover component setup.
