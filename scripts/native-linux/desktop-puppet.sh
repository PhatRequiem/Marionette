#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/runtime/desktop-puppet"
UNIT="marionette-puppet"
case "${1:-start}" in
  build)
    for command in qmake6 make g++; do
      command -v "$command" >/dev/null || { echo "Missing $command. See docs/active/current-operation/desktop-puppet.md" >&2; exit 1; }
    done
    [[ -f /usr/include/LayerShellQt/window.h ]] || { echo 'Missing layer-shell-qt development headers.' >&2; exit 1; }
    mkdir -p "$BUILD"
    cd "$BUILD"
    qmake6 "$ROOT/src/desktop-puppet/puppet.pro"
    make -j"${BUILD_JOBS:-2}"
    ;;
  test)
    mkdir -p "$BUILD/tests"
    cd "$BUILD/tests"
    qmake6 "$ROOT/tests/desktop-puppet/puppet-tests.pro"
    make -j"${BUILD_JOBS:-2}"
    QT_QPA_PLATFORMTHEME=basic QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software ./puppet-tests
    ;;
  start|preview)
    [[ -x "$BUILD/marionette-puppet" ]] || "$0" build
    if [[ "${1:-start}" == preview ]]; then
      exec "$BUILD/marionette-puppet" --preview
    fi
    exec "$BUILD/marionette-puppet"
    ;;
  background)
    [[ -x "$BUILD/marionette-puppet" ]] || "$0" build
    systemd-run --user --collect --unit="$UNIT" --description='Marionette desktop puppet preview' \
      --setenv=QT_QPA_PLATFORM=wayland --setenv="WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-1}" \
      "$BUILD/marionette-puppet"
    ;;
  stop) systemctl --user stop "$UNIT.service" ;;
  status) systemctl --user status "$UNIT.service" ;;
  *) echo "Usage: $0 {build|test|start|preview|background|stop|status}" >&2; exit 2 ;;
esac
