# Atlas MCP — Change Request Management

A full-stack **Model Context Protocol (MCP)** application for managing Atlas change requests using natural language. Includes a Python MCP server, React UI client, and a Python LLM client that integrates with any LLM (OpenAI, GitHub Copilot, Azure OpenAI, Claude).

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Server                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  FastMCP     │  │  FastAPI     │  │  LLM Processor   │  │
│  │  (MCP tools) │  │  (REST/SSE)  │  │  (Intent extrac) │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         └─────────────────┴──────────────────┬─┘            │
│                                    ┌─────────▼──────────┐   │
│                                    │  Atlas API Client  │   │
│                                    │  (Mock / Real)     │   │
│                                    └────────────────────┘   │
└──────────────────┬──────────────────────┬──────────────────┘
                   │ MCP SSE (/mcp/sse)   │ REST + SSE (/api)
        ┌──────────▼──────────┐  ┌────────▼────────────────┐
        │   LLM Client        │  │   React UI Client        │
        │   (Python CLI)      │  │   (Browser)              │
        │   Claude Desktop    │  │   Progress Pipeline      │
        │   GitHub Copilot    │  │   Chat Interface         │
        └─────────────────────┘  └─────────────────────────┘
```

### Processing Pipeline (React UI)
```
💬 Client  ──▶  🧠 LLM Processing  ──▶  ⚙️ MCP Server  ──▶  🌐 Atlas API  ──▶  ✅ Complete
```

---

## 📁 Project Structure

```
atlas-mcp/
├── mcp-server/                   # Python MCP Server + REST API bridge
│   ├── src/
│   │   ├── main.py               # Entry point (FastAPI + MCP mounted)
│   │   ├── mcp_server.py         # MCP tools (FastMCP)
│   │   ├── api_router.py         # FastAPI REST + SSE routes for React UI
│   │   ├── atlas_client.py       # Mock Atlas API client
│   │   ├── llm_processor.py      # LLM intent extraction (OpenAI-compatible)
│   │   ├── models.py             # Pydantic data models
│   │   └── config.py             # Environment-based configuration
│   ├── mock_data/
│   │   └── change_requests.json  # Pre-loaded mock change requests
│   ├── tests/
│   │   └── test_server.py        # Unit tests
│   ├── requirements.txt
│   ├── .env.dev                  # Development config
│   ├── .env.uit                  # User Integration Test config
│   └── .env.prod                 # Production config
│
├── client-ui/                    # React UI (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx  # Main chat UI with SSE streaming
│   │   │   ├── ProgressPipeline.tsx # Animated pipeline progress bar
│   │   │   ├── ChangeRequestCard.tsx # CR detail card
│   │   │   └── Header.tsx         # Environment switcher + server status
│   │   ├── services/api.ts        # API service (REST + SSE)
│   │   └── types/index.ts         # TypeScript types
│   ├── .env.development           # Dev API URL
│   └── .env.production            # Prod API URL
│
├── client-llm/                    # Python LLM CLI Client
│   ├── mcp_llm_client.py          # Interactive CLI + single-prompt mode
│   ├── requirements.txt
│   └── .env.example
│
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- An LLM API key (OpenAI, Azure OpenAI, or GitHub Copilot — optional, falls back to rule-based)

---

### 1. MCP Server Setup

```bash
cd mcp-server

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .\.venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment file
cp .env.example .env.dev
# Edit .env.dev and add your LLM_API_KEY (optional)
```

#### Start the server (Development)
```bash
APP_ENV=dev python -m src.main
# Server starts at http://localhost:8000
# API docs at http://localhost:8000/docs
# MCP SSE at http://localhost:8000/mcp/sse
```

#### Start for other environments
```bash
APP_ENV=uit  python -m src.main   # User Integration Test
APP_ENV=prod python -m src.main   # Production
```

#### Run in MCP stdio mode (for Claude Desktop)
```bash
APP_ENV=dev python -m src.main stdio
```

---

### 2. React UI Setup

```bash
cd client-ui

# Install dependencies
npm install

# Start development server
npm run dev
# Opens at http://localhost:5173
```

#### Build for production
```bash
npm run build
```

#### Environment configuration
| File | Usage |
|------|-------|
| `.env.development` | Dev (points to `localhost:8000`) |
| `.env.production`  | Prod (update `VITE_API_BASE_URL`) |

---

### 3. LLM Client Setup

```bash
cd client-llm

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env and set MCP_SERVER_URL and optionally LLM_API_KEY
```

#### Interactive mode
```bash
python mcp_llm_client.py
```

#### Single prompt
```bash
python mcp_llm_client.py --prompt "Create a change request with date 07/04/2026 - 07/06/2026 with title Apollo server upgrade"

python mcp_llm_client.py --prompt "What's the status of CHG123456" --env prod

python mcp_llm_client.py --prompt "Close CHG123456" --json
```

#### Options
```
--prompt, -p   Single prompt (non-interactive mode)
--env, -e      Environment: dev | uit | prod (default: dev)
--server, -s   MCP server URL (default: http://localhost:8000)
--mcp-sdk      Use native MCP SDK protocol instead of REST
--llm          Post-process response with LLM for friendlier output
--json         Output raw JSON (for programmatic/pipeline use)
```

---

## 💬 Sample Prompts

| Intent | Example Prompt |
|--------|---------------|
| Create CR | `"Create a change request with date 07/04/2026 - 07/06/2026 with title Apollo server upgrade"` |
| Add task | `"Add a deployment task to CHG123456 for deploying artifact git-tools app"` |
| Close CR | `"Update the status of CHG123456 to close"` |
| Check status | `"What's the status of CHG123456?"` |
| List CRs | `"Show me all open change requests in production"` |
| Update CR | `"Update CHG123456 risk level to high"` |

---

## 🌍 Environments

| Environment | Description | Atlas API | Mock Data |
|-------------|-------------|-----------|-----------|
| `dev` | Local development | `atlas-api.dev.example.com` | ✅ Yes |
| `uit` | User Integration Test | `atlas-api.uit.example.com` | ✅ Yes |
| `prod` | Production | `atlas-api.prod.example.com` | ❌ Real API |

Set `ATLAS_USE_MOCK=false` in the environment file to connect to a real Atlas API.

---

## 🔧 MCP Tools Reference

The MCP server exposes these tools (available to any MCP-compatible LLM):

| Tool | Description |
|------|-------------|
| `process_natural_language` | High-level NL handler — auto-routes based on intent |
| `create_change_request` | Create a new change request |
| `get_change_request_status` | Get status and details of a CR |
| `update_change_request` | Update fields on an existing CR |
| `add_task_to_change_request` | Add a task to a CR |
| `close_change_request` | Close a CR with optional reason |
| `list_change_requests` | List CRs with optional filters |

---

## 🤖 LLM Configuration

The server supports any OpenAI-compatible LLM API:

### OpenAI
```env
LLM_API_KEY=sk-...
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

### Azure OpenAI
```env
LLM_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
LLM_MODEL=gpt-4o
```

### GitHub Copilot (via API)
```env
LLM_API_KEY=your-github-token
LLM_API_BASE_URL=https://api.githubcopilot.com
LLM_MODEL=gpt-4o
```

> **Note:** If no LLM API key is configured, the server falls back to a built-in rule-based intent extractor that handles all common sample prompts automatically.

---

## 🔌 Integrating with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "atlas-mcp": {
      "command": "python",
      "args": ["-m", "src.main", "stdio"],
      "cwd": "/absolute/path/to/atlas-mcp/mcp-server",
      "env": {
        "APP_ENV": "dev",
        "PYTHONPATH": "/absolute/path/to/atlas-mcp/mcp-server"
      }
    }
  }
}
```

---

## 🔌 Integrating with GitHub Copilot (VS Code)

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "atlas-mcp": {
      "type": "sse",
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

---

## 🧪 Running Tests

```bash
cd mcp-server
source .venv/bin/activate
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## 🔗 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/stream` | POST | Process prompt with SSE pipeline updates |
| `/api/chat` | POST | Process prompt (synchronous) |
| `/api/change-requests` | GET | List change requests |
| `/api/change-requests/{id}` | GET | Get a specific CR |
| `/api/health` | GET | Server health check |
| `/mcp/sse` | GET | MCP SSE transport (for LLM clients) |
| `/docs` | GET | OpenAPI documentation |

---

## 🗂️ Mock Data

Pre-loaded change requests in `mcp-server/mock_data/change_requests.json`:

| ID | Title | Status | Environment |
|----|-------|--------|-------------|
| CHG123456 | Apollo Server Upgrade | open | prod |
| CHG123457 | Database Schema Migration | in_progress | prod |
| CHG123458 | Network Firewall Rule Update | closed | prod |
| CHG123459 | SSL Certificate Renewal | draft | prod |
| CHG123460 | Git-Tools Deployment | open | uit |

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| MCP Server | Python, [MCP SDK](https://github.com/modelcontextprotocol/python-sdk), FastMCP |
| API Bridge | FastAPI, Uvicorn, SSE |
| LLM | OpenAI API (any compatible provider) |
| React UI | React 18, TypeScript, Vite, Tailwind CSS |
| LLM Client | Python, httpx, openai |
| Data | In-memory mock store (JSON seed) |

---

## 🛠️ Development Tips

**Hot reload server:**
```bash
cd mcp-server && APP_ENV=dev uvicorn src.main:app --reload --port 8000
```

**Hot reload React UI:**
```bash
cd client-ui && npm run dev
```

**Inspect MCP tools:**
```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp/sse
```

**Direct API test:**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "what is the status of CHG123456", "environment": "dev"}'
```
