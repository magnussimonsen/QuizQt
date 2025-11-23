#!/bin/bash
# Convenience wrapper to build the executable using PyInstaller and QuizQt.spec
# Usage: from repo root run `bash build/build_quizqt.sh` (or make it executable and run ./build/build_quizqt.sh)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_CMD="python3"
if [ -d "../.venv" ]; then
    PYTHON_CMD="../.venv/bin/python3"
elif [ -d ".venv" ]; then
    PYTHON_CMD=".venv/bin/python3"
fi

if ! "$PYTHON_CMD" -m pip show pyinstaller >/dev/null 2>&1; then
	echo "PyInstaller not found. Installing into current environment..."
	"$PYTHON_CMD" -m pip install --upgrade pip
	"$PYTHON_CMD" -m pip install pyinstaller
fi

echo "Building executable with PyInstaller (QuizQt.spec)..."
# Build command: python3 -m PyInstaller QuizQt.spec (run via venv if available)
"$PYTHON_CMD" -m PyInstaller QuizQt.spec

if [ -f "dist/QuizQt/QuizQt" ]; then
	echo "Build complete: dist/QuizQt/QuizQt"
else
	echo "ERROR: Build did not produce dist/QuizQt/QuizQt"
	exit 1
fi
