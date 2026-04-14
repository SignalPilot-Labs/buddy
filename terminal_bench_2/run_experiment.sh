#!/usr/bin/env bash
# Runs a terminal-bench experiment fork against one or more tasks.
# Usage: ./run_experiment.sh <fork_name> <task1> [task2 ...]
# Example: ./run_experiment.sh caveman hello-world
# Example: ./run_experiment.sh lean write-compressor overfull-hbox
set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TB_BIN="/home/agentuser/.local/bin/tb"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMINAL_BENCH_2_DIR="${REPO_DIR}/terminal_bench_2"
TASKS_DIR="tasks/tasks-run2"
FORKS_PREFIX="autofyn_agent_"
JOBS_DIR="jobs"
SYMLINK_BASE="/tmp/tb2"
MODEL="anthropic/claude-opus-4-6"
CONCURRENCY=1

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <fork_name> <task1> [task2 ...]" >&2
    exit 1
fi

FORK_NAME="$1"
shift
TASKS=("$@")

if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    echo "Error: CLAUDE_CODE_OAUTH_TOKEN is not set." >&2
    exit 1
fi

FORK_DIR="${TERMINAL_BENCH_2_DIR}/${FORKS_PREFIX}${FORK_NAME}"
if [[ ! -d "${FORK_DIR}" ]]; then
    echo "Error: fork directory not found: ${FORK_DIR}" >&2
    exit 1
fi

DATASET_PATH="${TERMINAL_BENCH_2_DIR}/${TASKS_DIR}"

TASK_IDS=()
for TASK in "${TASKS[@]}"; do
    TASK_DIR="${DATASET_PATH}/${TASK}"
    if [[ ! -d "${TASK_DIR}" ]]; then
        echo "Error: task directory not found: ${TASK_DIR}" >&2
        exit 1
    fi
    TASK_IDS+=("${TASK}")
done

# ---------------------------------------------------------------------------
# Setup caveman fixture (idempotent)
# ---------------------------------------------------------------------------
"${TERMINAL_BENCH_2_DIR}/setup_caveman_fixture.sh"

# ---------------------------------------------------------------------------
# Point per-fork symlink at the chosen fork (avoids race conditions)
# ---------------------------------------------------------------------------
SYMLINK_PARENT="${SYMLINK_BASE}-${FORK_NAME}"
SYMLINK_PATH="${SYMLINK_PARENT}/terminal_bench"
mkdir -p "${SYMLINK_PARENT}"
ln -sfn "${FORK_DIR}" "${SYMLINK_PATH}"
echo "Symlink: ${SYMLINK_PATH} -> ${FORK_DIR}"

# ---------------------------------------------------------------------------
# Build and run the tb command
# ---------------------------------------------------------------------------
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
JOB_NAME="${FORK_NAME}-${TIMESTAMP}"
OUTPUT_DIR="${TERMINAL_BENCH_2_DIR}/${JOBS_DIR}"

TB_ARGS=(
    "run"
    "-p" "${DATASET_PATH}"
)

for TASK_ID in "${TASK_IDS[@]}"; do
    TB_ARGS+=("-t" "${TASK_ID}")
done

TB_ARGS+=(
    "--agent-import-path" "terminal_bench.agent:AutoFynAgent"
    "-m" "${MODEL}"
    "--output-path" "${OUTPUT_DIR}"
    "--run-id" "${JOB_NAME}"
    "--n-concurrent" "${CONCURRENCY}"
    "--n-attempts" "1"
    "--global-agent-timeout-sec" "3600"
)

echo "Running tb job: ${JOB_NAME}"
echo "Tasks: ${TASKS[*]}"
echo "Fork:  ${FORK_NAME}"
echo ""

PYTHONPATH="${SYMLINK_PARENT}" "${TB_BIN}" "${TB_ARGS[@]}"

echo ""
echo "Job output directory: ${OUTPUT_DIR}/${JOB_NAME}"
