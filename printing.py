import sys


GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
YELLOW = "\033[93m"


def print_response(response: dict):
	msg_type: str = response.get("type", "")
	status: int = response.get("status", 0)
	message: str = response.get("message", "")

	if msg_type.startswith("FILE_"):
		color = YELLOW
	elif int(status) == 200:
		color = GREEN
	else:
		color = RED

	reset = RESET

	sys.stdout.write(f"\n{color}[{status}] {message}{reset}\n\n")
	sys.stdout.flush()


def print_prompt():
	sys.stdout.write(">>> ")
	sys.stdout.flush()


def print_error(message: str):
	sys.stdout.write(f"\n{RED}{message}{RESET}\n\n")
	sys.stdout.flush()


def print_info(message: str):
	sys.stdout.write(f"\n{YELLOW}{message}{RESET}\n\n")
	sys.stdout.flush()
