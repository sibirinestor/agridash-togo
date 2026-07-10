#!/bin/bash
set -e

PORT=${PORT:-7860}

exec gunicorn dashboard.app:server --bind 0.0.0.0:$PORT --timeout 120 --workers 2
