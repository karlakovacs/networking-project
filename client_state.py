import os
import shutil


CLIENT_FILES_DIR = "client_files"


class ClientState:
	def __init__(self):
		self.username: str = None
		self.files: dict[str, dict[str, bool]] = {}  # file: str -> { locked_by: str | None, viewing: bool }
		os.makedirs(CLIENT_FILES_DIR, exist_ok=True)
		self.local_directory: str = None

	def handle_response(self, message_json: dict):
		msg_type: str = message_json["type"]
		status: int = message_json.get("status", 0)
		payload: dict = message_json.get("payload", {})

		match msg_type:
			case "AUTH_RESPONSE":
				self.handle_auth_response(status, payload)
			case "VIEW_RESPONSE":
				self.handle_view_response(status, payload)
			case "LOCK_RESPONSE":
				self.handle_lock_response(status, payload)
			case "UPDATE_RESPONSE":
				self.handle_update_response(status, payload)
			case "RELEASE_RESPONSE":
				self.handle_release_response(status, payload)
			case "ADD_RESPONSE":
				self.handle_add_response(status, payload)
			case "DELETE_RESPONSE":
				self.handle_delete_response(status, payload)

			case "FILE_ADDED":
				self.handle_file_added(payload)
			case "FILE_DELETED":
				self.handle_file_deleted(payload)
			case "FILE_LOCKED":
				self.handle_file_locked(payload)
			case "FILE_RELEASED":
				self.handle_file_released(payload)
			case "FILE_UPDATED":
				self.handle_file_updated(payload)

			case _:
				pass

	def handle_auth_response(self, status: int, payload: dict):
		if status == 200:
			username = payload.get("username")
			self.username = username
			self.local_directory = os.path.join(CLIENT_FILES_DIR, self.username)
			self.remove_local_directory()
			os.makedirs(self.local_directory, exist_ok=True)
			files: dict = payload.get("files", {})
			for file, info in files.items():
				self.files[file] = {"locked_by": info.get("locked_by"), "viewing": False}

	def handle_view_response(self, status: int, payload: dict):
		if status == 200:
			file = payload.get("file")
			content = payload.get("content")
			self.save_file(file, content)
			self.add_file_to_local_list(file)
			self.files[file]["viewing"] = True

	def handle_lock_response(self, status: int, payload: dict):
		if status == 200:
			file = payload.get("file")
			content = payload.get("content")
			if file:
				self.save_temp_file(file, content)
				if file not in self.files:
					self.files[file] = {}
				self.files[file]["locked_by"] = self.username

	def handle_update_response(self, status: int, payload: dict):
		if status == 200:
			pass

	def handle_release_response(self, status: int, payload: dict):
		if status == 200:
			file = payload.get("file")
			self.delete_temp_file(file)
			if file in self.files:
				self.files[file]["locked_by"] = None

	def handle_add_response(self, status: int, payload: dict):
		if status == 200:
			file = payload.get("file")
			self.add_file_to_local_list(file)
			path = os.path.join(self.local_directory, file)
			if os.path.exists(path):
				os.remove(path)

	def handle_delete_response(self, status: int, payload: dict):
		if status == 200:
			file = payload.get("file")
			self.delete_file(file)

	def handle_file_added(self, payload: dict):
		file = payload.get("file")
		self.add_file_to_local_list(file)

	def handle_file_deleted(self, payload: dict):
		file = payload.get("file")
		self.delete_file(file)

	def handle_file_locked(self, payload: dict):
		file = payload.get("file")
		user = payload.get("user")
		if file:
			self.add_file_to_local_list(file)
			self.files[file]["locked_by"] = user

	def handle_file_released(self, payload: dict):
		file = payload.get("file")
		if file and file in self.files:
			self.files[file]["locked_by"] = None

	def handle_file_updated(self, payload: dict):
		file = payload.get("file")
		content = payload.get("content")
		if file and content and self.files.get(file, {}).get("viewing"):
			self.save_file(file, content)

	def save_file(self, file: str, content: str):
		path = os.path.join(self.local_directory, file)
		with open(path, "w", encoding="utf-8") as f:
			f.write(content)

	def get_temp_file_path(self, file: str):
		name, ext = os.path.splitext(file)
		temp_file = f"{name}_temp{ext}"
		return os.path.join(self.local_directory, temp_file)

	def save_temp_file(self, file: str, content: str):
		path = self.get_temp_file_path(file)
		with open(path, "w", encoding="utf-8") as f:
			f.write(content)

	def delete_temp_file(self, file: str):
		path = self.get_temp_file_path(file)
		if os.path.exists(path):
			os.remove(path)

	def add_file_to_local_list(self, file: str):
		if file not in self.files:
			self.files[file] = {"locked_by": None, "viewing": False}

	def delete_file(self, file: str):
		if file in self.files:
			del self.files[file]
		path = os.path.join(self.local_directory, file)
		if os.path.exists(path):
			os.remove(path)

	def remove_local_directory(self):
		if self.local_directory is not None and os.path.exists(self.local_directory):
			shutil.rmtree(self.local_directory)
