from pydantic import BaseModel, Field
from mcp_client import McpClientConfig


class AgentConfig(BaseModel):
    name: str = Field(description="The name of the agent")
    mcp_client_config: McpClientConfig = Field(
        description="The configuration for the MCP client")
    llm_api_key: str = Field(default="", description="API key for the LLM service")
    llm_base_url: str = Field(
        default="https://api.deepseek.com", description="Base URL for the LLM API")
    llm_model: str = Field(
        default="deepseek-chat", description="LLM model name")
    task: str = Field(
        default="", description="The task for the agent to accomplish")
    initial_commands: list[str] = Field(
        default_factory=list,
        description="Initial chat commands to send (e.g., /give commands)")
    team_size: int = Field(
        default=1, description="Number of agents in the team. 1 = solo mode")
    team_timeout: float = Field(
        default=600.0, description="Max seconds before forcing team exit")
    clear_inventory: bool = Field(
        default=False, description="Clear bot inventory before starting (via RCON)")
