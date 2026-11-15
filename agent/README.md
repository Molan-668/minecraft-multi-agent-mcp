# Agent

This folder provides skeleton code for agent implementation. A simple MCP client has been integrated to control the agent body and keep track of the in-game chat messages.

## Introduction

The main logic lives in `agent.py`. `Agent.run()` starts the MCP session, runs `_pre_loop()` once (setup before the cognition loop—e.g. initial messages or tools), then repeats `_loop_once()` (sense–think–act; implement your agent here) with a short rest between iterations, and finally calls `_post_loop()` once (cleanup or persistence) before `stop()` tears down the session. Session wiring (`start` / `stop`) and the message-box background task are separate from pre/post loop hooks.

### Incoming Message Listening

The MCP server exposes a resource at `minecraft://incoming-messages`. Mineflayer pushes chat and whispers into a server-side buffer; when the client has subscribed to `minecraft://incoming-messages` (via `subscribe_resource`), the server sends a `notifications/resources/updated` event for that URI.

On `Agent.start()`, the client subscribes to that resource, drains any messages already buffered, then starts a background task (`_handle_update_message_box`). That task blocks on `McpClient.wait_for_incoming_messages()` until a notification arrives (or shutdown). Each wake-up calls `fetch_incoming_messages()`, which `read_resource`s the URI, parses the JSON array into `Message` objects, and appends them to `self.message_box`. Reading the resource clears the server buffer, so the client keeps the full history locally. In `_loop_once()`, read from `self.message_box` to react to new chat.

## Build MCP Server

Before running the agent + MCP client, remember to build the MCP server first. Check its README file for more details.

## Running the Agent

In this folder, first configure Python dependencies:

```bash
uv sync
```

Then, run the agent:

```bash
uv run python main.py \
  --name Steve \
  --game-host 127.0.0.1 \
  --game-port 25565 \
  --game-version 1.21.4 \
  --viewer-port 3000 \
  --inventory-viewer-port 4000
```

Omit flags you do not need; the values above are the defaults. Add `--debug` for verbose logging.

Note that you do not need to run the MCP server manually. Our client in this folder uses standard I/O to automatically start a connection.

### Important: Starting Fresh

Due to Minecraft world persistence, bot inventory carries over between sessions. Use these flags when you need a clean start:

| Flag | Purpose |
|------|---------|
| `--clear-inventory` | Clears bot inventory via RCON before starting (required for smelting "start with bare hands") |
| `--give "item count"` | Gives items via RCON (e.g., `--give "beef 1"` for cooking). Can be repeated. |
| `--team-size N` | Set team mode for multi-agent experiments. Agents broadcast `[REGISTER]` and wait for all `[DONE]` before exiting. |

To create a completely new Minecraft world (when inventory cannot be cleared), change `SAVE_NAME` in `sandbox/.env` and restart the server.

### Example Commands

```bash
# Chatting
uv run python main.py --name Steve --task "Say hello to everyone in chat"

# Smelting (from bare hands — use --clear-inventory)
uv run python main.py --name Steve --task "Smelt 1 raw iron into an iron ingot and place it in a chest" --clear-inventory

# Cooking (give raw meat; the agent will craft furnace, smelt, and produce cooked food)
uv run python main.py --name Steve --task "Cook 1 beef into cooked beef (steak)" --give "beef 1"

# MAS: Two agents collaborating on cake (run both simultaneously)
uv run python main.py --name Steve --task "Make a cake. You have milk_bucket x3. Alex has sugar,egg,wheat." --give "milk_bucket 3" --team-size 2 --clear-inventory
uv run python main.py --name Alex --viewer-port 3001 --inventory-viewer-port 4001 --task "Deliver sugar,egg,wheat to Steve." --give "sugar 2" --give "egg 1" --give "wheat 3" --team-size 2 --clear-inventory
```

## Viewing the Agent in Game

With [Prismarine Viewer](https://github.com/PrismarineJS/prismarine-viewer), after running the agent app, you can view the real-time agent behavior & surroundings in a browser. The default endpoint is http://127.0.0.1:3000.

## Viewing the Agent Inventory

With [Mineflayer Web Inventory](https://github.com/imharvol/mineflayer-web-inventory), after running the agent app, you can check its inventory in a browser as well. The default endpoint is http://127.0.0.1:4000.
