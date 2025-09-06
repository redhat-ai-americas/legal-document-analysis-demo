#!/usr/bin/env bash
set -euo pipefail

# Activate venv or create it if missing
if [ ! -d .venv ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi

exec streamlit run ./ui/streamlit_app.py
