"""Helper script that creates a Python virtual environment on Linux."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def run_command(command: list[str]) -> None:
	subprocess.run(command, check=True)


def launch_shell_with_venv(venv_path: Path) -> None:
	activate_script = venv_path / "bin" / "activate"
	if not activate_script.exists():
		raise FileNotFoundError(f"Activation script not found at {activate_script}")

	print("Dropping you into a shell with the virtual environment activated.")
	print("Type 'exit' to leave the environment.")
	bash_command = f"source '{activate_script}' && exec $SHELL"
	subprocess.run(["/bin/bash", "-c", bash_command], check=True)


def main() -> None:
	project_root = Path(__file__).resolve().parent
	venv_path = project_root / ".venv"
	python_exe = sys.executable

	print(f"Using Python interpreter: {python_exe}")
	run_command([python_exe, "-m", "venv", str(venv_path)])

	venv_python = venv_path / "bin" / "python"
	run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])

	requirements_file = project_root / "requirements.txt"
	if requirements_file.exists():
		run_command([str(venv_python), "-m", "pip", "install", "-r", str(requirements_file)])
	else:
		print("requirements.txt not found; skipping dependency installation.")

	launch_shell_with_venv(venv_path)


if __name__ == "__main__":
	main()
