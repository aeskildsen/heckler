#!/bin/bash
exec uv run --directory backend python start.py "$@"
