# Assignment - AI Agents in Minecraft

In this assignment, you are required to implement AI Agents that can interact with each other in a sandbox environment, specifically, a Minecraft game server, in order to accomplish several basic tasks like navigating, crafting, and cooking.

## Reference Codebase

The reference codebase includes 3 important folders:

1. `sandbox/`: Support simplified setup of a Minecraft game server with [Docker Compose](https://docs.docker.com/compose/), wrapping the popular [Docker Minecraft Server](https://docker-minecraft-server.readthedocs.io/en/latest/) project.
2. `mcp/`: Implement the agent body (in Typescript) to act in a Minecraft game. It includes basic operations like movement, block collection & placement, container examination & operation. An MCP server is exposed to the main agent logic, inspired by the existing [Minecraft MCP Server](https://github.com/yuniko-software/minecraft-mcp-server) project. This implementation introduces several enhancements upon the Mineflayer ecology (more details in the folder).
3. `agent/`: Implement the skeleton code of a basic AI Agent (in Python) plugging with the agent body MCP server. This folder is about the brain of the agent, which controls the agent body to decide the following actions to perform. **You will mainly work on this folder**.

## Minecraft World

To simply the environment complexity, the sandbox folder will create a world at peaceful difficulty, so hostile mobs do not jeopardize the agent behavior in this assignment. There will also be no health and hunger issues.

As [Prismarine Viewer](https://github.com/PrismarineJS/prismarine-viewer/issues/473) is currently experiencing rendering issues in higher Minecraft game versions, it is highly recommended to set the game version to <=`1.21.4`, if you intend to utilize the web viewer for the agent.

## Tasks

The implemented AI Agents should be able to **flexibly** (do not wire the behavior in code) handle the following tasks:

1. **Chatting**: Read chat messages from Minecraft chat channel, and respond when necessary.
2. **Smelting**: Start with bare hands, smelt 1 ore into an ingot and place it into a chest.
2. **Cooking**: When instructed to cook a specific food, the agent can start with bare hands, collect necessary resources, setup crafting tables and furnaces when necessary, and produce the target food.
3. ~~**Building**: When instructed to construct a simple building (e.g., a church, a pyramid) with certain materials (e.g., dirt, cobblestone, andesite, diorite), the agent can start with bare hands, collect required materials, and finish building.~~

### Cooking: Giving Initial Items

For the cooking task, since we have not yet supported mob attacking and direct tool using (e.g., use a hoe to create farmland), it is allowed to act like a god and give all **raw meat** and **crops** to the agent at the beginning.

**Note**: The `/give` command via Mineflayer's `bot.chat()` does not work in offline mode due to UUID mismatch. Instead, we use Docker's `rcon-cli` automatically through the `--give` flag:

```bash
uv run python main.py --name Steve --task "Cook 1 beef into steak" --give "beef 1"
```

The agent will use RCON to give items to the bot. Ensure your `.env` file has `ENABLE_RCON=true` and `RCON_PASSWORD=minecraft`.

To do this, you need to ensure your bot has op-level permissions from the game server. Check `sandbox/README.md` for more details.

Do not give the target food directly to the bot.
Do not give items like buckets or furnace, which your bot should be able to acquire by itself easily.

**Remember, we are testing our agent implementation. Give items only when it makes sense.**

### Starting Fresh (Important!)

Minecraft world persistence causes bot inventory to carry over between sessions. For tasks requiring "start with bare hands" (e.g., smelting), you have two options:

**Option A**: Use `--clear-inventory` flag — clears the bot's inventory via RCON at startup:
```bash
uv run python main.py --name Steve --task "Smelt 1 raw iron..." --clear-inventory
```

**Option B**: Create a new world — change `SAVE_NAME` in `sandbox/.env`:
```env
SAVE_NAME=my_new_world
```
Then restart the Docker server: `docker compose down && docker compose up -d`

### Self-evolving Behavior with Memory Management

Design the memory component for you agent. Then, test whether your agent's task performance and execution efficiency improves after gaining more experience.

For example, after cooking a steak and a cake, will your agent cook a mushroom stew faster because it gets familiar with the process of ingredient gathering and preparation?

### AI MAS

Since Minecraft already supports a centralized message channel in game, agent communication should be quite straightforward.

Suppose your agent implementation covers cooperation management, you can test whether adding multiple agents improves the task performance (e.g., success ratio) and handling efficiency.

Another thing you can test is how the agents can share their resources with each other. For example, what will happen if Agent X holds the milk bucket while Agent Y has sugar + wheat, and they both need to cook a cake?

To run multiple agents, use separate terminals with different `--name`, `--viewer-port`, and `--inventory-viewer-port` values. Use `--team-size N` for coordinated exit:

```bash
# Terminal 1 (Steve)
uv run python main.py --name Steve --task "Make a cake" --give "milk_bucket 3" --team-size 2 --clear-inventory

# Terminal 2 (Alex)
uv run python main.py --name Alex --viewer-port 3001 --inventory-viewer-port 4001 --task "Deliver ingredients" --give "sugar 2" --give "egg 1" --give "wheat 3" --team-size 2 --clear-inventory
```

See `agent/README.md` for more details.

### Comparison with BDI Agents

Recall how we map BDI Agents with existing ReAct-based AI Agents. When you implement your own AI Agents, anaylze your design in the BDI agent domain.
