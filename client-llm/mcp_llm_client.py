#!/usr/bin/env python3
"""
Atlas MCP LLM Client
====================
A standalone Python client that:
1. Connects to the Atlas MCP server via SSE (HTTP) transport
2. Wraps the connection with an LLM for natural language processing
3. Can be integrated into any LLM toolchain (GitHub Copilot, Claude, OpenAI Assistants, etc.)

Usage:
  python mcp_llm_client.py                        # Interactive CLI
  python mcp_llm_client.py --prompt "..."         # Single prompt
  python mcp_llm_client.py --prompt "..." --env prod
  python mcp_llm_client.py --stdio                # Connect via stdio (direct MCP)

Environment variables (or .env file):
  MCP_SERVER_URL  - MCP server base URL (default: http://localhost:8000)
  LLM_API_KEY     - OpenAI / Azure / Copilot API key
  LLM_MODEL       - Model name (default: gpt-4o-mini)
  APP_ENV         - dev | uit | prod
"""
import argparse
import asyncio
import json
import os
import sys
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1")
APP_ENV = os.getenv("APP_ENV", "dev")

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          Atlas MCP LLM Client — Change Request Manager       ║
║  Type your request in plain English. Type 'exit' to quit.    ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─── Direct REST client (uses the FastAPI bridge) ─────────────────────────────

class AtlasMcpRestClient:
    """
    Communicates with the Atlas MCP server via REST API.
    Uses Server-Sent Events for streaming responses.
    """

    def __init__(self, base_url: str, environment: str = "dev"):
        self.base_url = base_url.rstrip("/")
        self.environment = environment

    async def send_prompt(self, prompt: str, stream: bool = True) -> dict:
        """Send a natural language prompt to the MCP server."""
        payload = {"prompt": prompt, "environment": self.environment}

        if stream:
            return await self._stream_request(payload)
        else:
            return await self._sync_request(payload)

    async def _stream_request(self, payload: dict) -> dict:
        """Use SSE streaming endpoint."""
        result = {}
        pipeline_log = []

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat/stream",
                json=payload,
                headers={"Accept": "text/event-stream"},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line[6:].strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                        if data.get("type") == "result":
                            result = data
                        elif data.get("stage"):
                            pipeline_log.append(data)
                            _print_pipeline_stage(data)
                    except json.JSONDecodeError:
                        pass

        result["pipeline_log"] = pipeline_log
        return result

    async def _sync_request(self, payload: dict) -> dict:
        """Use synchronous POST endpoint."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """Check if the MCP server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False


# ─── MCP SDK Client (native MCP protocol) ────────────────────────────────────

async def _call_via_mcp_sdk(prompt: str, server_url: str, environment: str) -> str:
    """
    Use the official MCP Python SDK to call the process_natural_language tool.
    This demonstrates native MCP protocol usage (e.g., for Copilot / Claude Desktop).
    """
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        return "MCP SDK not installed. Run: pip install mcp"

    async with sse_client(f"{server_url}/mcp/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "process_natural_language",
                {"prompt": prompt, "environment": environment},
            )

            if result.content:
                return result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
            return "No response received"


# ─── LLM-enhanced client ──────────────────────────────────────────────────────

async def _enhance_with_llm(prompt: str, mcp_response: str) -> str:
    """
    Post-process the MCP response with an LLM for a friendlier output.
    Falls back gracefully if LLM is not configured.
    """
    if not LLM_API_KEY or LLM_API_KEY in ("your-llm-api-key-here", ""):
        return mcp_response

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL if LLM_BASE_URL != "https://api.openai.com/v1" else None)
        resp = await client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.3,
            max_tokens=512,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant summarizing change request management actions. "
                        "Given a technical response, provide a brief, friendly 1-2 sentence summary for the user. "
                        "Keep it professional and concise."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Original request: {prompt}\n\nSystem response:\n{mcp_response}\n\nProvide a brief friendly summary:",
                },
            ],
        )
        summary = resp.choices[0].message.content or mcp_response
        return f"{mcp_response}\n\n💬 **Summary:** {summary}"
    except Exception as e:
        return f"{mcp_response}\n\n[LLM enhancement unavailable: {e}]"


# ─── CLI helpers ──────────────────────────────────────────────────────────────

def _print_pipeline_stage(data: dict) -> None:
    """Pretty-print a pipeline stage update."""
    stage = data.get("stage", "")
    status = data.get("status", "")
    message = data.get("message", "")

    stage_emojis = {
        "client": "💬",
        "llm_processing": "🧠",
        "mcp_server": "⚙️ ",
        "atlas_api": "🌐",
        "complete": "✅",
        "error": "❌",
    }
    status_symbols = {
        "active": "⟳",
        "complete": "✓",
        "error": "✗",
        "idle": "○",
    }
    emoji = stage_emojis.get(stage, "•")
    symbol = status_symbols.get(status, "•")
    print(f"  {emoji} [{symbol}] {stage.replace('_', ' ').title()}: {message}", flush=True)


async def interactive_session(
    client: AtlasMcpRestClient,
    use_mcp_sdk: bool = False,
    enhance_with_llm: bool = False,
) -> None:
    """Run an interactive CLI session."""
    print(BANNER)
    print(f"  Connected to: {client.base_url}")
    print(f"  Environment:  {client.environment.upper()}")

    # Health check
    healthy = await client.health_check()
    if not healthy:
        print(f"\n⚠️  Warning: Cannot reach MCP server at {client.base_url}")
        print("   Make sure the server is running: cd mcp-server && python -m src.main\n")
    else:
        print("  Server:       ✅ Online\n")

    print("─" * 60)

    while True:
        try:
            prompt = input("\n🧑 You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye! 👋")
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "bye"):
            print("Goodbye! 👋")
            break

        print("\n📡 Processing pipeline:")
        print("─" * 40)

        try:
            if use_mcp_sdk:
                response_text = await _call_via_mcp_sdk(prompt, client.base_url, client.environment)
                result = {"response": response_text}
            else:
                result = await client.send_prompt(prompt, stream=True)

            print("─" * 40)

            response = result.get("response", "No response received.")
            if enhance_with_llm:
                response = await _enhance_with_llm(prompt, response)

            print(f"\n🤖 Atlas MCP:\n{response}")

        except httpx.ConnectError:
            print(f"\n❌ Cannot connect to {client.base_url}. Is the server running?")
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def single_prompt(
    client: AtlasMcpRestClient,
    prompt: str,
    use_mcp_sdk: bool = False,
    output_json: bool = False,
) -> None:
    """Process a single prompt (non-interactive)."""
    if not output_json:
        print(f"Processing: {prompt}\n")
        print("Pipeline:")

    try:
        if use_mcp_sdk:
            response_text = await _call_via_mcp_sdk(prompt, client.base_url, client.environment)
            result = {"response": response_text}
        else:
            result = await client.send_prompt(prompt, stream=not output_json)

        if output_json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nResponse:\n{result.get('response', 'No response')}")

    except Exception as e:
        if output_json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Atlas MCP LLM Client - Change Request Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mcp_llm_client.py
  python mcp_llm_client.py --prompt "Create a CR for Apollo upgrade 07/10/2026-07/12/2026"
  python mcp_llm_client.py --prompt "Status of CHG123456" --env prod
  python mcp_llm_client.py --prompt "Close CHG123456" --json
  python mcp_llm_client.py --mcp-sdk --prompt "List all open CRs"
        """,
    )
    parser.add_argument("--prompt", "-p", help="Single prompt to process (non-interactive)")
    parser.add_argument("--env", "-e", default=APP_ENV, choices=["dev", "uit", "prod"],
                        help="Target environment (default: dev)")
    parser.add_argument("--server", "-s", default=MCP_SERVER_URL,
                        help=f"MCP server URL (default: {MCP_SERVER_URL})")
    parser.add_argument("--mcp-sdk", action="store_true",
                        help="Use native MCP SDK (SSE) instead of REST API")
    parser.add_argument("--llm", action="store_true",
                        help="Enhance responses with LLM post-processing")
    parser.add_argument("--json", action="store_true", dest="output_json",
                        help="Output raw JSON (for programmatic use)")
    args = parser.parse_args()

    client = AtlasMcpRestClient(args.server, args.env)

    if args.prompt:
        asyncio.run(single_prompt(client, args.prompt, args.mcp_sdk, args.output_json))
    else:
        asyncio.run(interactive_session(client, args.mcp_sdk, args.llm))


if __name__ == "__main__":
    main()

