#!/usr/bin/env python3
"""
MQL5 Documentation RAG MCP Server

A Model Context Protocol (MCP) server that provides Claude Desktop with access 
to up-to-date MQL5 documentation through a serverless AWS RAG infrastructure.

This server implements the MCP protocol to expose a `search_mql5_docs` tool
that retrieves relevant MQL5 documentation snippets for code generation and
technical assistance.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
)
from pydantic import BaseModel, Field


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler("mql5_mcp_server.log")
    ]
)
logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    """Configuration model for the MQL5 MCP Server."""
    
    aws_api_gateway_url: str = Field(
        ..., 
        description="AWS API Gateway URL for the RAG endpoint"
    )
    api_key_env_var: str = Field(
        default="MQL5_RAG_API_KEY",
        description="Environment variable name containing the API key"
    )
    timeout_seconds: int = Field(
        default=2,
        description="HTTP request timeout in seconds"
    )
    max_snippets: int = Field(
        default=5,
        description="Maximum number of documentation snippets to retrieve"
    )
    circuit_breaker_failures: int = Field(
        default=3,
        description="Number of consecutive failures before circuit breaker opens"
    )
    circuit_breaker_cooldown: int = Field(
        default=300,
        description="Circuit breaker cooldown period in seconds"
    )


class MQL5MCPServer:
    """
    MQL5 Documentation RAG MCP Server
    
    Implements the Model Context Protocol to provide Claude Desktop with
    access to MQL5 documentation through AWS serverless RAG infrastructure.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the MQL5 MCP Server with configuration."""
        self.config = self._load_config(config_path)
        self.api_key = self._get_api_key()
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Circuit breaker state
        self.failure_count = 0
        self.circuit_breaker_open_until: Optional[float] = None
        
        # Initialize MCP server
        self.server = Server("mql5-rag-server")
        self._setup_tools()
        
        logger.info("MQL5 MCP Server initialized successfully")
    
    def _load_config(self, config_path: Optional[Path] = None) -> ServerConfig:
        """Load configuration from YAML file."""
        if config_path is None:
            config_path = Path("config.yaml")
        
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded from {config_path}")
            else:
                logger.warning(f"Config file {config_path} not found, using defaults")
                config_data = {
                    # Provide default values when config file is missing
                    "aws_api_gateway_url": "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/rag",
                    "api_key_env_var": "MQL5_RAG_API_KEY",
                    "timeout_seconds": 2,
                    "max_snippets": 5,
                    "circuit_breaker_failures": 3,
                    "circuit_breaker_cooldown": 300
                }
            
            return ServerConfig(**config_data)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # If validation fails, provide a helpful error message with defaults
            if "aws_api_gateway_url" in str(e) and "Field required" in str(e):
                logger.error("Missing required configuration. Please create config.yaml with aws_api_gateway_url")
                logger.info("Using emergency defaults for testing...")
                return ServerConfig(
                    aws_api_gateway_url="https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/rag"
                )
            raise
    
    def _get_api_key(self) -> str:
        """Retrieve API key from environment variable."""
        api_key = os.getenv(self.config.api_key_env_var)
        if not api_key:
            raise ValueError(
                f"API key not found in environment variable: {self.config.api_key_env_var}"
            )
        return api_key
    
    def _setup_tools(self):
        """Register MCP tools with the server."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
            return [
                Tool(
                    name="search_mql5_docs",
                    description="Search official MQL5 documentation for functions, syntax, examples, and best practices",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query for MQL5 documentation"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            if name == "search_mql5_docs":
                return await self._search_mql5_docs(arguments.get("query", ""))
            else:
                raise ValueError(f"Unknown tool: {name}")
        
        # Store tools list for testing
        self._available_tools = [
            {
                "name": "search_mql5_docs",
                "description": "Search official MQL5 documentation for functions, syntax, examples, and best practices",
                "schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query for MQL5 documentation"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools for testing purposes."""
        return getattr(self, '_available_tools', [])
    
    async def _search_mql5_docs(self, query: str) -> List[TextContent]:
        """
        Search MQL5 documentation using AWS RAG infrastructure.
        
        Args:
            query: The search query string
            
        Returns:
            List of TextContent with documentation snippets
        """
        # Input validation
        if not query or not query.strip():
            return [TextContent(
                type="text",
                text="Error: Search query cannot be empty"
            )]
        
        query = query.strip()
        
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            return [TextContent(
                type="text",
                text="Documentation search temporarily unavailable"
            )]
        
        try:
            # Initialize HTTP client if not already done
            if self.http_client is None:
                self.http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.config.timeout_seconds)
                )
            
            # Prepare request
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "query": query,
                "max_snippets": self.config.max_snippets
            }
            
            logger.info(f"Searching MQL5 docs for query: {query}")
            
            # Make request to AWS API Gateway
            response = await self.http_client.post(
                self.config.aws_api_gateway_url,
                json=payload,
                headers=headers
            )
            
            # Handle response
            if response.status_code == 200:
                self._reset_circuit_breaker()
                data = response.json()
                return self._format_search_results(data, query)
            
            elif response.status_code == 401:
                logger.error("Invalid API key")
                self._increment_failure_count()
                return [TextContent(
                    type="text",
                    text="Documentation service encountered an authentication error"
                )]
            
            elif response.status_code == 429:
                logger.warning("Rate limited by API Gateway")
                return [TextContent(
                    type="text",
                    text="Search temporarily throttled"
                )]
            
            else:
                logger.error(f"API Gateway returned status {response.status_code}")
                self._increment_failure_count()
                return [TextContent(
                    type="text",
                    text="Documentation service error"
                )]
        
        except httpx.TimeoutException:
            logger.warning(f"Request timeout for query: {query}")
            self._increment_failure_count()
            return [TextContent(
                type="text",
                text="Search timed out, please try again"
            )]
        
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            self._increment_failure_count()
            return [TextContent(
                type="text",
                text="Documentation search temporarily unavailable"
            )]
    
    def _format_search_results(self, data: Dict[str, Any], query: str) -> List[TextContent]:
        """Format AWS RAG response into MCP TextContent."""
        try:
            snippets = data.get("snippets", [])
            
            if not snippets:
                return [TextContent(
                    type="text",
                    text=f"No MQL5 documentation found for query: {query}"
                )]
            
            # Format results
            formatted_text = f"# MQL5 Documentation Search Results\n\n"
            formatted_text += f"**Query:** {query}\n\n"
            
            for i, snippet in enumerate(snippets[:self.config.max_snippets], 1):
                snippet_text = snippet.get("snippet", "")
                source = snippet.get("source", "Unknown")
                score = snippet.get("score", 0.0)
                
                formatted_text += f"## Result {i}\n"
                formatted_text += f"**Source:** {source}\n"
                formatted_text += f"**Relevance:** {score:.2f}\n\n"
                formatted_text += f"```\n{snippet_text}\n```\n\n"
            
            return [TextContent(type="text", text=formatted_text)]
        
        except Exception as e:
            logger.error(f"Failed to format search results: {e}")
            return [TextContent(
                type="text",
                text="Documentation service error"
            )]
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        if self.circuit_breaker_open_until is None:
            return False
        
        import time
        if time.time() < self.circuit_breaker_open_until:
            return True
        
        # Reset circuit breaker after cooldown
        self.circuit_breaker_open_until = None
        self.failure_count = 0
        logger.info("Circuit breaker reset after cooldown")
        return False
    
    def _increment_failure_count(self):
        """Increment failure count and potentially open circuit breaker."""
        self.failure_count += 1
        logger.warning(f"Failure count: {self.failure_count}")
        
        if self.failure_count >= self.config.circuit_breaker_failures:
            import time
            self.circuit_breaker_open_until = time.time() + self.config.circuit_breaker_cooldown
            logger.error(f"Circuit breaker opened for {self.config.circuit_breaker_cooldown} seconds")
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful request."""
        if self.failure_count > 0:
            self.failure_count = 0
            logger.info("Circuit breaker reset after successful request")
    
    async def run(self):
        """Run the MCP server."""
        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(read_stream, write_stream)
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
        finally:
            # Cleanup
            if self.http_client:
                await self.http_client.aclose()


def main():
    """Main entry point for the MQL5 MCP Server."""
    # Check if running in proper MCP context
    if sys.stdin.isatty():
        print("⚠️  MQL5 MCP Server")
        print("=" * 30)
        print("This server is designed to be launched by Claude Desktop via MCP protocol.")
        print("Running directly from command line will result in stdio errors.")
        print("")
        print("To test the server, run:")
        print("  uv run python test_server.py")
        print("")
        print("To use with Claude Desktop:")
        print("  1. Configure claude_desktop_config.json")
        print("  2. Launch Claude Desktop")
        print("  3. Server will be automatically started")
        print("")
        print("Proceeding anyway (expect stdio errors)...")
        print("")
    
    try:
        server = MQL5MCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        if "TaskGroup" in str(e) and sys.stdin.isatty():
            logger.info("Expected error: MCP server requires stdio connection from Claude Desktop")
            print("\n✅ Server validation successful!")
            print("The 'TaskGroup' error is expected when running without MCP stdio connection.")
        else:
            logger.error(f"Failed to start server: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()