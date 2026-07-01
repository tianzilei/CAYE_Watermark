#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
VENV_DIR="$PROJECT_DIR/.venv"
STAMP_FILE="$VENV_DIR/.caye_webui_installed"

cd "$PROJECT_DIR"

version_ok() {
  local python_bin="$1"
  "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
}

choose_python() {
  local candidates=()

  if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
    candidates+=("${CONDA_PREFIX}/bin/python")
  fi

  if command -v python >/dev/null 2>&1; then
    candidates+=("$(command -v python)")
  fi

  if command -v python3 >/dev/null 2>&1; then
    candidates+=("$(command -v python3)")
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if version_ok "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "错误：未找到可用的 Python 3.10+。请先激活 Conda 环境或安装新版本 Python。" >&2
  exit 1
}

PYTHON_BIN="$(choose_python)"

recreate_venv=false
if [[ -x "$VENV_DIR/bin/python" ]]; then
  if ! version_ok "$VENV_DIR/bin/python"; then
    recreate_venv=true
  fi
elif [[ -d "$VENV_DIR" ]]; then
  recreate_venv=true
fi

if [[ "$recreate_venv" == true ]]; then
  echo "检测到旧虚拟环境，正在重建..."
  rm -rf "$VENV_DIR"
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "创建虚拟环境..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if [[ ! -f "$STAMP_FILE" || "$PROJECT_DIR/pyproject.toml" -nt "$STAMP_FILE" || "$PROJECT_DIR/setup.py" -nt "$STAMP_FILE" ]]; then
  echo "安装或更新项目依赖..."
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -e "$PROJECT_DIR"
  touch "$STAMP_FILE"
fi

echo "启动 CAYE Watermark WebUI..."
exec "$VENV_DIR/bin/python" -m caye_watermark.webui
