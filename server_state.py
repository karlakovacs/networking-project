import json
import os
import socket


SERVER_FILES_DIR = "server_files"


class ServerState:
	def __init__(self):
		self.clients: dict[socket.socket, str] = {}  # socket -> username
		self.files: dict[str, dict[str, set[str]]] = {}  # file: str -> { locked_by: str | None, viewers: set[str] }
		os.makedirs(SERVER_FILES_DIR, exist_ok=True)
		self.initialize_files()

	def initialize_files(self):
		for filename in os.listdir(SERVER_FILES_DIR):
			if os.path.isfile(os.path.join(SERVER_FILES_DIR, filename)):
				self.files[filename] = {"locked_by": None, "viewers": set()}

	def is_authenticated(self, sock: socket.socket):
		return sock in self.clients

	def get_username_by_socket(self, sock: socket.socket):
		return self.clients.get(sock)

	def file_exists(self, file: str):
		return file in self.files

	def is_file_locked(self, file: str):
		return self.files[file]["locked_by"] is not None

	def is_file_locked_by_user(self, file: str, user: str):
		return self.files[file]["locked_by"] == user

	def can_delete_file(self, file: str):
		return self.file_exists(file) and not self.is_file_locked(file)

	def add_viewer(self, file: str, user: str):
		self.files[file]["viewers"].add(user)

	def remove_viewer(self, file: str, user: str):
		self.files[file]["viewers"].discard(user)

	def notify_all(self, data: dict, exclude_username: str = None):
		for sock, user in self.clients.items():
			if user != exclude_username:
				self.send(sock, data)

	def notify_viewers(self, file: str, data: dict):
		viewers = self.files[file]["viewers"]
		for sock, user in self.clients.items():
			if user in viewers:
				self.send(sock, data)

	def send(self, sock: socket.socket, data: dict):
		message = self.serialize(data)
		sock.sendall(message.encode())

	def serialize(self, data: dict):
		return json.dumps(data)

	def make_response(self, response_type: str, status: int, message: str, payload: dict = None):
		return {"type": response_type, "status": status, "message": message, "payload": payload or {}}

	def handle_request(self, sock: socket.socket, message_json: dict):
		request_type = message_json["type"]
		payload = message_json.get("payload", {})

		if not self.is_authenticated(sock) and request_type != "AUTH":
			return self.make_response(f"{request_type}_RESPONSE", 403, "Nu sunteți autentificat.")

		match request_type:
			case "AUTH":
				return self.handle_auth(sock, payload)
			case "VIEW":
				return self.handle_view(sock, payload)
			case "LOCK":
				return self.handle_lock(sock, payload)
			case "UPDATE":
				return self.handle_update(sock, payload)
			case "RELEASE":
				return self.handle_release(sock, payload)
			case "ADD":
				return self.handle_add(sock, payload)
			case "DELETE":
				return self.handle_delete(sock, payload)
			case _:
				return self.make_response("ERROR", 400, "Comandă necunoscută.")

	def handle_auth(self, sock: socket.socket, payload: dict):
		username = payload.get("username")
		if not username:
			return self.make_response("AUTH_RESPONSE", 400, "Lipsește numele de utilizator.")

		if username in self.clients.values():
			return self.make_response("AUTH_RESPONSE", 400, "Utilizator deja conectat.")

		self.clients[sock] = username

		return self.make_response(
			"AUTH_RESPONSE",
			200,
			"Autentificare reușită.",
			{"username": username, "files": {f: {"locked_by": info["locked_by"]} for f, info in self.files.items()}},
		)

	def handle_view(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")

		if not self.file_exists(file):
			return self.make_response("VIEW_RESPONSE", 404, "Fișierul nu există.")

		if username in self.files[file]["viewers"]:
			return self.make_response("VIEW_RESPONSE", 400, "Fișierul este deja în vizualizare.")

		self.add_viewer(file, username)

		with open(os.path.join("server_files", file), "r", encoding="utf-8") as f:
			content = f.read()

		return self.make_response(
			"VIEW_RESPONSE", 200, "Fișier descărcat cu succes.", {"file": file, "content": content}
		)

	def handle_lock(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")

		if not self.file_exists(file):
			return self.make_response("LOCK_RESPONSE", 404, "Fișierul nu există.")

		if self.is_file_locked(file):
			return self.make_response("LOCK_RESPONSE", 403, "Fișierul este deja blocat.")

		self.files[file]["locked_by"] = username

		with open(os.path.join("server_files", file), "r", encoding="utf-8") as f:
			content = f.read()

		broadcast = {
			"type": "FILE_LOCKED",
			"status": 200,
			"message": f"{username} a blocat {file}.",
			"payload": {"file": file, "user": username},
		}
		self.notify_all(broadcast, exclude_username=username)

		return self.make_response("LOCK_RESPONSE", 200, "Fișier blocat cu succes.", {"file": file, "content": content})

	def handle_release(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")

		if not self.file_exists(file):
			return self.make_response("RELEASE_RESPONSE", 404, "Fișierul nu există.")

		if not self.is_file_locked_by_user(file, username):
			return self.make_response("RELEASE_RESPONSE", 403, "Nu aveți lock pe fișier.")

		self.files[file]["locked_by"] = None

		broadcast = {
			"type": "FILE_RELEASED",
			"status": 200,
			"message": f"{username} a eliberat {file}.",
			"payload": {"file": file, "user": username},
		}
		self.notify_all(broadcast, exclude_username=username)

		return self.make_response("RELEASE_RESPONSE", 200, "Fișier deblocat.", {"file": file})

	def handle_update(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")
		content = payload.get("content")

		if not self.file_exists(file):
			return self.make_response("UPDATE_RESPONSE", 404, "Fișierul nu există.")

		if not self.is_file_locked_by_user(file, username):
			return self.make_response("UPDATE_RESPONSE", 403, "Nu aveți permisiunea de a modifica acest fișier.")

		with open(os.path.join("server_files", file), "w", encoding="utf-8") as f:
			f.write(content)

		self.notify_viewers(
			file,
			{
				"type": "FILE_UPDATED",
				"status": 200,
				"message": f"{username} a actualizat fișierul {file}.",
				"payload": {"file": file, "user": username, "content": content},
			},
		)

		return self.make_response("UPDATE_RESPONSE", 200, "Fișier actualizat.", {"file": file})

	def handle_add(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")
		content = payload.get("content")

		if self.file_exists(file):
			return self.make_response("ADD_RESPONSE", 400, "Fișierul există deja. Redenumiți-l.")

		with open(os.path.join("server_files", file), "w", encoding="utf-8") as f:
			f.write(content)

		self.files[file] = {"locked_by": None, "viewers": set()}

		broadcast = {
			"type": "FILE_ADDED",
			"status": 200,
			"message": f"{username} a adăugat {file}.",
			"payload": {"file": file, "user": username},
		}
		self.notify_all(broadcast, exclude_username=username)

		return self.make_response("ADD_RESPONSE", 200, "Fișier adăugat.", {"file": file})

	def handle_delete(self, sock: socket.socket, payload: dict):
		username = self.get_username_by_socket(sock)
		file = payload.get("file")

		if not self.file_exists(file):
			return self.make_response("DELETE_RESPONSE", 404, "Fișierul nu există.")

		if self.is_file_locked(file):
			return self.make_response("DELETE_RESPONSE", 403, "Fișierul este blocat și nu poate fi șters.")

		os.remove(os.path.join("server_files", file))
		if file in self.files:
			del self.files[file]

		broadcast = {
			"type": "FILE_DELETED",
			"status": 200,
			"message": f"{username} a șters fișierul {file}.",
			"payload": {"file": file, "user": username},
		}
		self.notify_all(broadcast, exclude_username=username)

		return self.make_response("DELETE_RESPONSE", 200, "Fișier șters.", {"file": file})
	
	def cleanup_disconnected_user(self, username: str):
		for file, info in self.files.items():
			if info["locked_by"] == username:
				info["locked_by"] = None
				self.notify_all({
					"type": "FILE_RELEASED",
					"status": 200,
					"message": f"{username} s-a deconectat și a eliberat lock-ul pe {file}.",
					"payload": {"file": file, "user": username}
				})
			if username in info["viewers"]:
				info["viewers"].discard(username)
