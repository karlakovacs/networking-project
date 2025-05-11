import json
import os
import socket
import sys
import threading

from client_state import ClientState
from printing import print_error, print_info, print_prompt, print_response


state: ClientState = ClientState()

SERVER_ADDRESS = ("localhost", 12345)


def listen_to_server(sock: socket.socket):
	while True:
		try:
			data = sock.recv(4096)
			if not data:
				print_error("[CLIENT] Conexiune închisă de server.")
				print_prompt()
				break

			response: dict = json.loads(data.decode("utf-8"))
			print_response(response)
			state.handle_response(response)
			print_prompt()

		except OSError:
			break

		except Exception as e:
			print_error(f"[CLIENT] Eroare la ascultare: {e}")
			print_prompt()
			break


def handle_request(request: str) -> dict | None:
	tokens = request.strip().split(maxsplit=1)
	if not tokens:
		print_error("[CLIENT] Comandă invalidă.")
		print_prompt()
		return None

	command: str = tokens[0].upper()
	arg: str = tokens[1] if len(tokens) > 1 else None
	username: str = state.username
	payload: dict = {}

	match command:
		case "AUTH":
			if not arg:
				print_info("[CLIENT] Utilizare: AUTH <username>")
				print_prompt()
				return None
			payload["username"] = arg
			return {"type": "AUTH", "payload": payload}

		case "VIEW" | "LOCK" | "RELEASE" | "DELETE":
			if not arg:
				print_info(f"[CLIENT] Utilizare: {command} <nume_fisier>")
				print_prompt()
				return None
			payload["file"] = arg
			return {"type": command, "payload": payload}

		case "UPDATE":
			if not arg:
				print_info("[CLIENT] Utilizare: UPDATE <nume_fisier>")
				print_prompt()
				return None
			name, ext = os.path.splitext(arg)
			temp_filename = f"{name}_temp{ext}"

			temp_path = f"client_files/{username}/{temp_filename}"

			if not os.path.exists(temp_path):
				print_error(f"[CLIENT] Fișierul de editat nu există: {temp_path}")
				print_prompt()
				return None

			with open(temp_path, "r", encoding="utf-8") as f:
				content = f.read()

			payload["file"] = arg
			payload["content"] = content
			return {"type": "UPDATE", "payload": payload}

		case "ADD":
			if not arg:
				print_info("[CLIENT] Utilizare: ADD <nume_fisier_local>")
				print_prompt()
				return None

			path = f"client_files/{username}/{arg}"

			if not os.path.exists(path):
				print_error(f"[CLIENT] Fișierul nu există local: {path}")
				print_prompt()
				return None

			with open(path, "r", encoding="utf-8") as f:
				content = f.read()

			payload["file"] = arg
			payload["content"] = content
			return {"type": "ADD", "payload": payload}

		case "LIST":
			raspuns = "Lista de fisiere:\n"
			for f, info in state.files.items():
				lock = info.get("locked_by") or "-"
				viewing = "✓" if info.get("viewing") else "-"
				raspuns += f"- {f} | locked by: {lock} | viewing: {viewing}\n"
			print_info(raspuns.strip())
			print_prompt()
			return None

		case "HELP":
			print_info("""Comenzi disponibile:
- AUTH <username>           | autentificare
- VIEW <file>               | descarcă un fișier read-only
- LOCK <file>               | începe editarea unui fișier
- UPDATE <file>             | trimite modificările
- RELEASE <file>            | eliberează un fișier
- ADD <file>                | adaugă un fișier local pe server
- DELETE <file>             | șterge un fișier de pe server
- LIST                      | afișează lista locală de fișiere
- HELP                      | afișează comenzile disponibile
- EXIT                      | ieșire din aplicație""")
			print_prompt()
			return None

		case _:
			print_error(f"[CLIENT] Comandă necunoscută: {command}")
			print_prompt()
			return None


def main():
	client_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		client_socket.connect(SERVER_ADDRESS)
		print_info(f"[CLIENT] Conectat la {SERVER_ADDRESS}")

		broadcast_thread = threading.Thread(target=listen_to_server, args=(client_socket,), daemon=True)
		broadcast_thread.start()

		print_prompt()
		while True:
			try:
				request = sys.stdin.readline().strip()

				if request.upper() == "EXIT":
					break

				json_msg = handle_request(request)
				if json_msg:
					client_socket.sendall(json.dumps(json_msg).encode("utf-8"))

			except KeyboardInterrupt:
				break

	except ConnectionRefusedError:
		print_error(f"[CLIENT] Nu s-a putut conecta la {SERVER_ADDRESS}. Asigurați-vă că serverul rulează.")
		print_prompt()

	except Exception as e:
		print_error(f"[CLIENT] Eroare: {e}")
		print_prompt()

	finally:
		client_socket.close()
		state.remove_local_directory()
		print_info("[CLIENT] S-a închis.")


if __name__ == "__main__":
	main()
