#!/bin/sh
# Entrypoint that execs python directly so it receives signals as PID 1.
set -e

echo "Starting ${HOST_TYPE}:${PACKAGE_NAME} on port ${PORT:-default}..."

if [ "${HOST_TYPE}" = "agent" ]; then
    exec python -m "agents.${PACKAGE_NAME}"
elif [ "${HOST_TYPE}" = "vn_bridge" ]; then
    exec python -u agents/vn_bridge.py
else
    exec python -m "hosts.${PACKAGE_NAME}"
fi
