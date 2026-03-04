"""
Main Heckler application - orchestrates OSC, LLM, and WebSocket components.

This is a pure asyncio application with no blocking operations.
"""

import asyncio
import base64
import logging
import signal

from .config import Config
from .llm import OllamaClient
from .memes import generate_meme_image, save_meme_to_disk
from .osc_server import HecklerOSCServer
from .websocket import WebSocketBroadcaster

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
        memes_enabled: bool = True,
        memes_save_to_disk: bool = False,
        memes_output_directory: str = "generated_memes",
        memes_min_interval: int = 5,
        memes_max_interval: int = 10,
    ):
        """Initialize Heckler application."""
        self.ollama_host = ollama_host
        self.ollama_port = ollama_port
        self.ollama_model = ollama_model
        self.osc_host = osc_host
        self.osc_port = osc_port
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.memes_enabled = memes_enabled
        self.memes_save_to_disk = memes_save_to_disk
        self.memes_output_directory = memes_output_directory
        self.memes_min_interval = memes_min_interval
        self.memes_max_interval = memes_max_interval

        # Components
        self.llm: OllamaClient | None = None
        self.osc_server: HecklerOSCServer | None = None
        self.ws_broadcaster: WebSocketBroadcaster | None = None

        # Shutdown event
        self.shutdown_event = asyncio.Event()

    async def _handle_clear(self):
        """
        Handle clear command from browser.

        Clears all LLM context and resets state before a new performance.
        """
        logger.info("Handling clear command - resetting LLM context")
        if self.llm:
            self.llm.clear_context()

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
                if template and args and self.memes_enabled:
                    try:
                        # Generate meme image with MemePy
                        logger.info(f"Generating meme: {template} with args: {args}")
                        image_bytes = generate_meme_image(template, args)

                        # Optionally save to disk
                        if self.memes_save_to_disk:
                            filepath = save_meme_to_disk(
                                image_bytes, self.memes_output_directory, template
                            )
                            logger.info(f"Saved meme to {filepath}")

                        # Base64 encode for WebSocket transmission
                        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

                        # Broadcast enhanced meme message with image data
                        await self.ws_broadcaster.broadcast(
                            {
                                "type": "meme",
                                # "template": template,
                                "content": image_base64,
                                "caption": response.get("caption"),
                            }
                        )

                    except Exception as e:
                        logger.error(f"Failed to generate meme: {e}", exc_info=True)
                        # Fallback to text response
                        await self.ws_broadcaster.broadcast_text(
                            f"[Meme generation failed: {e}]"
                        )
                else:
                    # Malformed meme response or memes disabled, log and send fallback
                    logger.warning(
                        f"Malformed meme response or memes disabled: {response}"
                    )
                    await self.ws_broadcaster.broadcast_text(
                        "[LLM meme response malformed or disabled]"
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
            host=self.ollama_host,
            port=self.ollama_port,
            model=self.ollama_model,
            meme_min_interval=self.memes_min_interval,
            meme_max_interval=self.memes_max_interval,
        )

        # Health check (non-fatal for development)
        if not await self.llm.health_check():
            logger.warning("Ollama health check failed - will use mock responses")
            logger.warning("This is OK for development/testing without Ollama")

        # Initialize WebSocket broadcaster
        self.ws_broadcaster = WebSocketBroadcaster(host=self.ws_host, port=self.ws_port)
        # Set up clear callback to clear LLM context
        self.ws_broadcaster.on_clear = self._handle_clear
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
    # Load configuration
    config = Config()

    # Configure logging level from config
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = HecklerApp(
        ollama_host=config.ollama_host,
        ollama_port=config.ollama_port,
        ollama_model=config.ollama_model,
        osc_host=config.osc_host,
        osc_port=config.osc_port,
        ws_host=config.ws_host,
        ws_port=config.ws_port,
        memes_enabled=config.memes_enabled,
        memes_save_to_disk=config.memes_save_to_disk,
        memes_output_directory=config.memes_output_directory,
        memes_min_interval=config.memes_min_interval,
        memes_max_interval=config.memes_max_interval,
    )

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, app.signal_handler)

    # Run
    await app.run()


if __name__ == "__main__":
    asyncio.run(main())
