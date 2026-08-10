#!/bin/bash
set -e
{
    uv venv --python 3.13
    source .venv/bin/activate
    UV_LINK_MODE=copy uv sync
} > /dev/null 2>&1