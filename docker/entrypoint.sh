#!/bin/sh
# Entrypoint that execs python directly so it receives signals as PID 1.
set -e

echo "Starting ${HOST_TYPE}:${PACKAGE_NAME} on port ${PORT:-default}..."

if [ "${HOST_TYPE}" = "agent" ] || [ "${HOST_TYPE}" = "vn_bridge" ]; then
    exec python -m "agents.${PACKAGE_NAME}"
else
    exec python -m "hosts.${PACKAGE_NAME}"
fi
