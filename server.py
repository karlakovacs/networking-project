import json
import socket
import threading

from printing import print_error, print_info
from server_state import ServerState


SERVER_HOST = "localhost"
SERVER_PORT = 12345

state = ServerState()


def handle_client(client_socket: socket.socket, client_address):
	print_info(f"[INFO] Conexiune nouă de la {client_address}")
	state.clients[client_socket] = ""

	try:
		while True:
			data = client_socket.recv(4096)
			if not data:
				break

			try:
				message_json = json.loads(data.decode("utf-8"))
			except json.JSONDecodeError:
				error = state.make_response("ERROR", 400, "Mesaj JSON invalid.")
				client_socket.sendall(json.dumps(error).encode("utf-8"))
				continue

			response = state.handle_request(client_socket, message_json)
			if response:
				client_socket.sendall(json.dumps(response).encode("utf-8"))

	except ConnectionResetError:
		print_info(f"[INFO] Clientul {client_address} s-a deconectat forțat.")
	except Exception as e:
		print_error(f"[ERROR] Eroare cu clientul {client_address}: {e}")
	finally:
		print_info(f"[INFO] Conexiune închisă cu {client_address}")
		username = state.clients.pop(client_socket, None)
		if username:
			state.cleanup_disconnected_user(username)
		client_socket.close()


def main():
	server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	server_socket.bind((SERVER_HOST, SERVER_PORT))
	server_socket.listen(10)

	print_info(f"[INFO] Serverul ascultă pe {SERVER_HOST}:{SERVER_PORT}")

	while True:
		client_socket, client_address = server_socket.accept()
		client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
		client_thread.start()


if __name__ == "__main__":
	main()
