"""
Main Heckler application - orchestrates OSC, LLM, and WebSocket components.

This is a pure asyncio application with no blocking operations.
"""

import asyncio
import logging
import signal

from .llm import OllamaClient
from .osc_server import HecklerOSCServer
from .websocket import WebSocketBroadcaster

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


class HecklerApp:
    """
    Main Heckler application that coordinates all components.

    Flow:
    1. OSC server receives code from SuperCollider
    2. LLM client generates commentary
    3. WebSocket broadcasts response to browser
    """

    def __init__(
        self,
        ollama_host: str = "192.168.3.241",
        ollama_port: int = 11434,
        ollama_model: str = "mistral:7b",
        osc_host: str = "127.0.0.1",
        osc_port: int = 5005,
        ws_host: str = "0.0.0.0",
        ws_port: int = 8765,
    ):
        """Initialize Heckler application."""
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.ollama_model = ollama_model
        self.osc_host = osc_host
        self.osc_port = osc_port
        self.ws_host = ws_host
        self.ws_port = ws_port

        # Components
        self.llm: OllamaClient | None = None
        self.osc_server: HecklerOSCServer | None = None
        self.ws_broadcaster: WebSocketBroadcaster | None = None

        # Shutdown event
        self.shutdown_event = asyncio.Event()

    async def _handle_code_evaluation(self, code: str):
        """
        Handle code evaluation from SuperCollider.

        This is called asynchronously when OSC message arrives.
        """
        logger.info(f"Processing code evaluation: {code[:60]}...")

        try:
            # Generate LLM commentary
            response = await self.llm.generate_commentary(code)

            # Broadcast to browser
            if response.get("response_type") == "text":
                content = response.get("content")
                if content:
                    await self.ws_broadcaster.broadcast_text(content)
                else:
                    # Malformed text response, log and send fallback
                    logger.warning(
                        f"Malformed text response (missing content): {response}"
                    )
                    await self.ws_broadcaster.broadcast_text("[LLM response malformed]")

            elif response.get("response_type") == "meme":
                template = response.get("template")
                args = response.get("args")
                if template and args:
                    await self.ws_broadcaster.broadcast_meme(
                        template=template, args=args, caption=response.get("caption")
                    )
                else:
                    # Malformed meme response, log and send fallback
                    logger.warning(f"Malformed meme response: {response}")
                    await self.ws_broadcaster.broadcast_text(
                        "[LLM meme response malformed]"
                    )
            else:
                logger.warning(f"Unknown response type: {response}")
                await self.ws_broadcaster.broadcast_text("[Unknown LLM response]")

            logger.info(
                f"✓ Sent {response.get('response_type', 'unknown')} response to browser"
            )

        except Exception as e:
            logger.error(f"Error processing code evaluation: {e}", exc_info=True)
            # Send error message to browser
            await self.ws_broadcaster.broadcast_text(f"[Error: {e}]")

    async def start(self):
        """Start all components."""
        logger.info("=" * 60)
        logger.info("Starting Heckler - Live Coding Commentary System")
        logger.info("=" * 60)

        # Initialize LLM client
        logger.info(f"Connecting to Ollama at {self.ollama_host}:{self.ollama_port}")
        self.llm = OllamaClient(
            host=self.ollama_host, port=self.ollama_port, model=self.ollama_model
        )

        # Health check (non-fatal for development)
        if not await self.llm.health_check():
            logger.warning("Ollama health check failed - will use mock responses")
            logger.warning("This is OK for development/testing without Ollama")

        # Initialize WebSocket broadcaster
        self.ws_broadcaster = WebSocketBroadcaster(host=self.ws_host, port=self.ws_port)
        await self.ws_broadcaster.start()

        # Initialize OSC server with code handler
        self.osc_server = HecklerOSCServer(
            host=self.osc_host,
            port=self.osc_port,
            code_handler=self._handle_code_evaluation,
        )
        await self.osc_server.start()

        logger.info("=" * 60)
        logger.info("✓ Heckler is ready!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info(
            f"  1. Open browser to WebSocket client (ws://localhost:{self.ws_port})"
        )
        logger.info(
            f"  2. Send OSC messages to {self.osc_host}:{self.osc_port} on /code"
        )
        logger.info("  3. Evaluate code in SuperCollider")
        logger.info("")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

    async def stop(self):
        """Stop all components."""
        logger.info("")
        logger.info("Shutting down Heckler...")

        if self.osc_server:
            await self.osc_server.stop()

        if self.ws_broadcaster:
            await self.ws_broadcaster.stop()

        logger.info("✓ Shutdown complete")

    async def run(self):
        """Run the application until interrupted."""
        await self.start()

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        await self.stop()

    def signal_handler(self):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal")
        self.shutdown_event.set()


async def main():
    """Entry point for the application."""
    app = HecklerApp(
        ollama_host="192.168.3.241",
        ollama_port=11434,
        ollama_model="mistral:7b",
        osc_host="127.0.0.1",
        osc_port=5005,
        ws_host="0.0.0.0",
        ws_port=8765,
    )

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.signal_handler)

    # Run
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
