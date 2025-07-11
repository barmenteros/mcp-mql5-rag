# MQL5 Documentation RAG MCP Server

A **Model Context Protocol (MCP) server** that provides Claude Desktop with access to up-to-date MQL5 documentation through a serverless AWS RAG (Retrieval-Augmented Generation) infrastructure.

## Overview

This MCP server implements the `search_mql5_docs` tool, allowing Claude Desktop to retrieve relevant MQL5 documentation snippets for accurate code generation and technical assistance.

## Features

- 🔍 **Real-time MQL5 Documentation Search** - Retrieves up-to-date documentation snippets
- ⚡ **Low Latency** - Optimized for <500ms average response time
- 🛡️ **Robust Error Handling** - Circuit breaker pattern for graceful degradation
- 🔐 **Secure** - API key-based authentication with AWS API Gateway
- 📊 **Monitoring** - Comprehensive logging and error reporting

## Prerequisites

- **Python 3.10+**
- **uv package manager** (recommended for dependency management)
- **AWS Account** with deployed RAG infrastructure
- **Claude Desktop** with MCP support

## Installation

### 1. Clone and Set Up Project

```bash
# Clone the repository
git clone <repository-url>
cd mcp-mql5-rag

# Create virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install dependencies
uv add "mcp[cli]" httpx pyyaml pydantic
```

### 2. Configuration

#### Environment Variables

Set your AWS API Gateway API key:

```bash
# Linux/macOS
export MQL5_RAG_API_KEY="your-api-gateway-key-here"

# Windows
set MQL5_RAG_API_KEY=your-api-gateway-key-here
```

#### Configuration File

Update `config.yaml` with your AWS API Gateway URL:

```yaml
aws_api_gateway_url: "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/rag"
```

### 3. Claude Desktop Integration

Add the following to your Claude Desktop configuration file:

**Location:** 
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "mql5-docs": {
      "command": "uv",
      "args": ["run", "python", "-m", "mql5_mcp_server"],
      "cwd": "/path/to/mcp-mql5-rag",
      "env": {
        "MQL5_RAG_API_KEY": "your-api-gateway-key-here"
      }
    }
  }
}
```

## Usage

Once configured, the `search_mql5_docs` tool will be available in Claude Desktop:

```
Search MQL5 documentation for ArrayResize function
```

Claude will automatically use the tool when MQL5-related questions are asked.

## Development

### Project Structure

```
mcp-mql5-rag/
├── src/
│   └── mql5_mcp_server.py     # Main MCP server implementation
├── config.yaml               # Configuration file
├── requirements.txt           # Dependencies (for compatibility)
├── pyproject.toml            # Python project configuration
└── README.md                 # This file
```

### Running Locally

```bash
# Run the server directly
uv run python -m mql5_mcp_server

# Or install and run
uv pip install -e .
mql5-mcp-server
```

### Testing

```bash
# Install development dependencies
uv add --dev pytest pytest-asyncio pyright ruff black

# Run tests
uv run pytest

# Type checking
uv run pyright

# Code formatting
uv run black src/
uv run ruff check src/
```

## Error Handling

The server implements robust error handling:

- **Timeout Protection**: 2-second timeout on AWS API calls
- **Circuit Breaker**: Automatic fallback after 3 consecutive failures
- **Graceful Degradation**: User-friendly error messages
- **Comprehensive Logging**: Detailed logs for debugging

### Common Error Messages

| Message | Cause | Solution |
|---------|-------|----------|
| "Documentation search temporarily unavailable" | Circuit breaker open or AWS API down | Wait for cooldown period |
| "Search timed out, please try again" | Network timeout | Retry the request |
| "Documentation service encountered an authentication error" | Invalid API key | Check API key configuration |

## Configuration Reference

### config.yaml Options

```yaml
# Required: AWS API Gateway URL
aws_api_gateway_url: "https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/rag"

# Optional: Environment variable for API key (default: MQL5_RAG_API_KEY)
api_key_env_var: "MQL5_RAG_API_KEY"

# Optional: Request timeout in seconds (default: 2)
timeout_seconds: 2

# Optional: Maximum snippets to retrieve (default: 5)
max_snippets: 5

# Optional: Circuit breaker configuration
circuit_breaker_failures: 3    # Failures before opening (default: 3)
circuit_breaker_cooldown: 300  # Cooldown in seconds (default: 300)
```

## Troubleshooting

### Check Server Status

```bash
# View server logs
tail -f mql5_mcp_server.log

# Test configuration
uv run python -c "from mql5_mcp_server import MQL5MCPServer; server = MQL5MCPServer(); print('✅ Configuration valid')"
```

### Common Issues

1. **ImportError: No module named 'mcp'**
   - Solution: `uv add "mcp[cli]"`

2. **API Key not found**
   - Solution: Set the `MQL5_RAG_API_KEY` environment variable

3. **Connection timeout**
   - Solution: Check AWS API Gateway URL and network connectivity

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `uv run ruff check src/` and `uv run pytest`
5. Submit a pull request

---

**Related Projects:**
- [MQL5 RAG AWS Infrastructure](../aws-infrastructure)
- [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)