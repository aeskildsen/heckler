"""
WebSocket broadcast manager for sending LLM responses to browser display.
"""

import json
import logging
from typing import Any

import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger(__name__)


class WebSocketBroadcaster:
    """
    Manages WebSocket connections and broadcasts LLM responses to all connected clients.

    Handles multiple browser connections (e.g., if you want display on multiple screens).
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """
        Initialize WebSocket broadcaster.

        Args:
            host: IP to bind to (0.0.0.0 = all interfaces)
            port: WebSocket port
        """
        self.host = host
        self.port = port
        self.clients: set[WebSocketServerProtocol] = set()
        self.server: websockets.WebSocketServer | None = None
        self.on_clear = None  # Callback for clear command

    async def _register_client(self, websocket: WebSocketServerProtocol):
        """Register a new WebSocket client."""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def _unregister_client(self, websocket: WebSocketServerProtocol):
        """Unregister a disconnected WebSocket client."""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def _handle_client(self, websocket: WebSocketServerProtocol):
        """Handle a WebSocket connection."""
        await self._register_client(websocket)

        try:
            # Keep connection alive and handle any incoming messages
            async for message in websocket:
                # Handle incoming commands from browser
                logger.debug(f"Received message from client: {message}")

                try:
                    data = json.loads(message)
                    command = data.get("command")

                    if command == "clear":
                        logger.info("Received clear command from browser")
                        # Trigger clear callback if set
                        if hasattr(self, 'on_clear') and self.on_clear:
                            await self.on_clear()
                        # Broadcast clear confirmation to all clients
                        await self.broadcast({"type": "clear"})
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {message}")

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self._unregister_client(websocket)

    async def start(self):
        """Start the WebSocket server."""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        self.server = await websockets.serve(self._handle_client, self.host, self.port)

        logger.info(f"✓ WebSocket server listening on ws://{self.host}:{self.port}")
        logger.info("  Waiting for browser connections...")

    async def stop(self):
        """Stop the WebSocket server."""
        if self.server:
            logger.info("Stopping WebSocket server...")
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    async def broadcast(self, message: dict[str, Any]):
        """
        Broadcast a message to all connected clients.

        Args:
            message: Dict to be JSON-serialized and sent to all clients
        """
        if not self.clients:
            logger.warning("No clients connected - message not sent")
            return

        # Serialize message
        json_message = json.dumps(message)

        # Send to all clients concurrently
        disconnected_clients = set()

        for client in self.clients:
            try:
                await client.send(json_message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                disconnected_clients.add(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            await self._unregister_client(client)

        logger.info(f"Broadcast message to {len(self.clients)} client(s)")

    async def broadcast_text(self, content: str):
        """Convenience method to broadcast text commentary."""
        await self.broadcast({"type": "text", "content": content})

    async def broadcast_meme(
        self, template: str, args: list[str], caption: str | None = None
    ):
        """Convenience method to broadcast meme response."""
        await self.broadcast(
            {"type": "meme", "template": template, "args": args, "caption": caption}
        )
