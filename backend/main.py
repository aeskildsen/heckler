import requests
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

IP = "127.0.0.1"
PORT = 5005


def code_handler(address, *args):
    print(f"CODE RECEIVED: {args}")


def catchall_handler(address, *args):
    print(f"CATCHALL: Message received at {address} with arguments: {args}")


requests.get("http://localhost:8000/startup")

if __name__ == "__main__":
    dispatcher = Dispatcher()
    dispatcher.map("/x", code_handler)
    dispatcher.set_default_handler(catchall_handler)

    print("Starting the OSC server...")

    server = BlockingOSCUDPServer((IP, PORT), dispatcher)

    print(f"Listening on {server.server_address}")

    server.serve_forever()
