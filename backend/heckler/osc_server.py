"""
Async OSC server for receiving SuperCollider code evaluations.

Uses python-osc's AsyncIOOSCUDPServer for non-blocking message reception.
"""

import asyncio
import logging
from typing import Awaitable, Callable

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

logger = logging.getLogger(__name__)


class HecklerOSCServer:
    """
    Async OSC server that receives SuperCollider code blocks and triggers LLM commentary.

    This server doesn't block - it can receive new OSC messages while Ollama is processing
    previous requests.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5005,
        code_handler: Callable[[str], Awaitable[None]] | None = None,
    ):
        """
        Initialize OSC server.

        Args:
            host: IP to bind to (use "0.0.0.0" for all interfaces)
            port: OSC port to listen on
            code_handler: Async callback function that receives evaluated code strings
        """
        self.host = host
        self.port = port
        self.code_handler = code_handler

        # Create dispatcher
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/code", self._handle_code_message)
        self.dispatcher.set_default_handler(self._handle_unknown_message)

        # Server instance (created on start)
        self.server: AsyncIOOSCUDPServer | None = None
        self.transport: asyncio.DatagramTransport | None = None

    def _handle_code_message(self, address: str, *args):
        """
        Handle incoming /code messages from SuperCollider.

        Expected format: /code "{ SinOsc.ar(440) }.play;"

        Note: This must be a regular function (not async) because python-osc
        dispatcher doesn't support async handlers. We spawn async tasks manually.
        """
        if not args:
            logger.warning(f"Received empty /code message from {address}")
            return

        # Extract code string (first argument)
        code = str(args[0])
        logger.info(f"Received code block ({len(code)} chars): {code[:60]}...")

        # Call the registered handler (if any)
        if self.code_handler:
            try:
                # Spawn as background task so we don't block OSC reception
                asyncio.create_task(self.code_handler(code))
            except Exception as e:
                logger.error(f"Error in code handler: {e}", exc_info=True)

    def _handle_unknown_message(self, address: str, *args):
        """Handle any OSC messages not mapped to specific handlers."""
        logger.debug(f"Unknown OSC message: {address} {args}")

    async def start(self):
        """Start the async OSC server."""
        logger.info(f"Starting OSC server on {self.host}:{self.port}")

        # Create server
        self.server = AsyncIOOSCUDPServer(
            (self.host, self.port), self.dispatcher, asyncio.get_event_loop()
        )

        # Start listening
        self.transport, _ = await self.server.create_serve_endpoint()

        logger.info(f"✓ OSC server listening on {self.host}:{self.port}")
        logger.info("  Waiting for SuperCollider code evaluations on /code...")

    async def stop(self):
        """Stop the OSC server."""
        if self.transport:
            logger.info("Stopping OSC server...")
            self.transport.close()
            self.transport = None
            self.server = None

    def set_code_handler(self, handler: Callable[[str], Awaitable[None]]):
        """Set or update the code handler callback."""
        self.code_handler = handler
