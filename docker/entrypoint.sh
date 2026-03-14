#!/bin/sh
# Entrypoint that execs python directly so it receives signals as PID 1.
set -e

if [ "${HOST_TYPE}" = "agent" ]; then
    exec python -m "agents.${PACKAGE_NAME}"
else
    exec python -m "hosts.${PACKAGE_NAME}"
fi
