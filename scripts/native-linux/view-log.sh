#!/usr/bin/env bash
set -euo pipefail
printf 'Marionette conversation log\n%s\n\n' "$1"
tail --pid="$2" --sleep-interval=0.2 --lines=+1 --follow -- "$1"
printf '\nChat ended. This log is saved. Press Enter to close.\n'
read -r _ || true
