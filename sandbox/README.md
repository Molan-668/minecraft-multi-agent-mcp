# Minecraft Server

We use [Docker Minecraft Server](https://docker-minecraft-server.readthedocs.io/) to manage our worlds. A Docker Compose file `compose.yaml` with a `.env` environment variable file are specified.

## Requirements

To utilize this server, you need to have [Docker](https://www.docker.com/) installed first. And that's it!

## Steps

1. Create a `.env` file besides `compose.yaml` and add necessary parameters there. You can refer to configurations in the `env_example` file. **Note that you need to add your bot's names in the `OPS` field to give them op-level permissions if you want to use `/give` to give initial items to your bot.**
2. `docker compose up -d`
3. Wait for about 30s. A `minecraft_data/` folder will be created. Most of your configurations in the `.env` file will go to the `server.properties` file inside (You can also tell by reading the `compose.yaml` file a bit).
4. Now we are all set! Start your Minecraft client and connects via the `<IP>:<port>` you configure.
5. You can stop the server completely by running `docker compose down`. If you modify your configurations in the `.env` file, you can also refresh `server.properties` by stopping and then starting the docker compose file.

## Updating `compose.yaml`

If you want to add new configurations to the server, check the official documentation page of Docker Minecraft Server [here](https://docker-minecraft-server.readthedocs.io/en/latest/variables/). For reference, you may also find the official documenatation page of `server.properties` helpful [here](https://minecraft.wiki/w/Server.properties).
