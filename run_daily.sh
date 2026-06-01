#!/bin/bash
# Daily scrape wrapper for cron.
#
# Activates the local venv, runs scrape_daily.py, appends to data/cron.log.
# Designed to be invoked from cron — handles spaces in path and PATH variable.

set -eu

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/data/cron.log"
mkdir -p "$SCRIPT_DIR/data"

{
  echo
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') starting daily scrape ===="
  "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scrape_daily.py"
  echo "==== $(date '+%Y-%m-%d %H:%M:%S') done ===="
} >> "$LOG_FILE" 2>&1
