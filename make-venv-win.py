"""Helper script that creates a Windows-friendly Python virtual environment."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def run_command(command: list[str]) -> None:
	"""Run a subprocess command and bubble up errors."""
	subprocess.run(command, check=True)


def launch_shell_with_venv(venv_path: Path) -> None:
	"""Open a new Command Prompt with the virtual environment activated."""
	activate_bat = venv_path / "Scripts" / "activate.bat"
	if not activate_bat.exists():
		raise FileNotFoundError(f"Activation script not found at {activate_bat}")

	print("Starting Command Prompt with the virtual environment activated…")
	print("Close the shell or type 'exit' when you are done.")
	subprocess.run(["cmd.exe", "/k", str(activate_bat)], check=True)


def main() -> None:
	project_root = Path(__file__).resolve().parent
	venv_path = project_root / ".venv"
	python_exe = sys.executable

	print(f"Using Python interpreter: {python_exe}")
	run_command([python_exe, "-m", "venv", str(venv_path)])

	venv_python = venv_path / "Scripts" / "python.exe"
	run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])

	requirements_file = project_root / "requirements.txt"
	if requirements_file.exists():
		run_command([str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)])
	else:
		print("requirements.txt not found; skipping dependency installation.")

	launch_shell_with_venv(venv_path)


if __name__ == "__main__":
	main()
