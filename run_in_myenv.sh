#!/bin/bash
set -euo pipefail

# Usage: ./run_in_myenv.sh <script_filename.py> [args...]
if [ $# -lt 1 ]; then
  echo "Usage: $0 <script_filename.py> [args...]"
  exit 1
fi

SCRIPT_FILENAME="$1"
shift  # remove the filename from the arg list; the rest are for the script

VENV_PATH="myenv"

if [ ! -d "$VENV_PATH" ]; then
  echo "Virtual environment not found at $VENV_PATH"
  exit 1
fi

# activate venv
source "$VENV_PATH/bin/activate"

# run python, forwarding all remaining args
python3 "$SCRIPT_FILENAME" "$@"
status=$?

deactivate || true
exit $status
