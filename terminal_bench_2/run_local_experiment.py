#!/usr/bin/env python3
"""Run AutoFyn fork locally against terminal-bench-2 tasks."""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_DIR: Path = Path(__file__).parent.resolve()
TASKS_DIR: Path = REPO_DIR / "tasks" / "tasks-run2"
JOBS_DIR: Path = REPO_DIR / "jobs"

CONTAINER_WORKDIR: str = "/app"
CONTAINER_LOGS_DIR: str = "/logs"
CONTAINER_AGENT_DIR: str = "/logs/agent"
CONTAINER_VERIFIER_DIR: str = "/logs/verifier"
CONTAINER_TESTS_DIR: str = "/tests"
REWARD_FILE_PATH: str = "/logs/verifier/reward.txt"

PLATFORM: str = "linux/amd64"
DEFAULT_AGENT_TIMEOUT_SEC: float = 900.0
DEFAULT_VERIFIER_TIMEOUT_SEC: float = 900.0
FALLBACK_MODEL: str = "claude-opus-4-6"
FALLBACK_MAX_TURNS: int = 75
DOCKER_BUILD_TIMEOUT_SEC: float = 600.0
DOCKER_MISC_TIMEOUT_SEC: float = 30.0

BASELINE_REWARDS: dict[str, float] = {
    "raman-fitting": 0.25,
    "fix-code-vulnerability": 0.0,
    "gpt2-codegolf": 0.0,
}

STDOUT_TRUNCATE_LEN: int = 10000
STDERR_TRUNCATE_LEN: int = 5000
DEFAULT_FORK_DIR: str = "autofyn_agent"
DEFAULT_TIMEOUT_MULTIPLIER: float = 1.0
HEREDOC_DELIMITER: str = "AUTOFYN_HEREDOC_EOF"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AutoFyn fork locally against terminal-bench-2 tasks."
    )
    parser.add_argument(
        "--fork-dir",
        default=DEFAULT_FORK_DIR,
        help="Path to fork directory (resolved relative to REPO_DIR)",
    )
    parser.add_argument(
        "--tasks",
        required=True,
        help="Comma-separated task names to run",
    )
    parser.add_argument(
        "--timeout-multiplier",
        type=float,
        default=DEFAULT_TIMEOUT_MULTIPLIER,
        help="Multiplier for agent and verifier timeouts",
    )
    return parser.parse_args()


def validate_environment() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        print("ERROR: CLAUDE_CODE_OAUTH_TOKEN environment variable is not set.")
        sys.exit(1)
    return token


def load_task_config(task_dir: Path) -> dict:
    with open(task_dir / "task.toml", "rb") as f:
        return tomllib.load(f)


def load_fork_config(fork_dir: Path) -> tuple[str, int, str]:
    model = FALLBACK_MODEL
    max_turns = FALLBACK_MAX_TURNS
    system_prompt = ""

    constants_path = fork_dir / "constants.py"
    if constants_path.exists():
        constants_text = constants_path.read_text()
        model_match = re.search(r'DEFAULT_MODEL\s*:\s*str\s*=\s*["\']([^"\']+)["\']', constants_text)
        if model_match:
            model = model_match.group(1)
        turns_match = re.search(r"DEFAULT_MAX_TURNS\s*:\s*int\s*=\s*(\d+)", constants_text)
        if turns_match:
            max_turns = int(turns_match.group(1))

    prompt_path = fork_dir / "prompts" / "single_session.md"
    if prompt_path.exists():
        system_prompt = prompt_path.read_text()

    return model, max_turns, system_prompt


def build_task_image(task_dir: Path, task_name: str) -> str:
    image_tag = f"tb2-{task_name}"
    env_dir = task_dir / "environment"
    subprocess.run(
        [
            "docker", "build",
            "--platform", PLATFORM,
            "-t", image_tag,
            str(env_dir),
        ],
        capture_output=True,
        text=True,
        timeout=DOCKER_BUILD_TIMEOUT_SEC,
        check=True,
    )
    return image_tag


def start_container(image: str) -> str:
    result = subprocess.run(
        ["docker", "run", "-d", "--platform", PLATFORM, image, "sleep", "infinity"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def stop_container(container_id: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_id],
        capture_output=True,
        text=True,
    )


def docker_exec(
    container_id: str,
    command: list[str],
    timeout: float,
    env: dict[str, str] | None,
) -> subprocess.CompletedProcess[str]:
    cmd: list[str] = ["docker", "exec"]
    if env:
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
    cmd += [container_id] + command
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def docker_cp_to_container(src: Path, container_id: str, dest: str) -> None:
    subprocess.run(
        ["docker", "cp", str(src), f"{container_id}:{dest}"],
        capture_output=True,
        text=True,
        check=True,
    )


def docker_cp_from_container(container_id: str, src: str, dest: Path) -> None:
    subprocess.run(
        ["docker", "cp", f"{container_id}:{src}", str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )


def setup_container_dirs(container_id: str) -> None:
    docker_exec(
        container_id,
        ["mkdir", "-p", CONTAINER_AGENT_DIR, CONTAINER_VERIFIER_DIR, CONTAINER_TESTS_DIR],
        timeout=DOCKER_MISC_TIMEOUT_SEC,
        env=None,
    )


def copy_test_files(container_id: str, task_dir: Path) -> None:
    tests_dir = task_dir / "tests"
    for test_file in tests_dir.iterdir():
        if test_file.is_file():
            docker_cp_to_container(
                test_file, container_id, CONTAINER_TESTS_DIR + "/" + test_file.name
            )


def _write_file_to_container(container_id: str, content: str, dest_path: str) -> None:
    write_cmd = [
        "docker", "exec", container_id, "bash", "-c",
        f"cat > {dest_path} << '{HEREDOC_DELIMITER}'\n{content}\n{HEREDOC_DELIMITER}",
    ]
    subprocess.run(write_cmd, capture_output=True, text=True, timeout=DOCKER_MISC_TIMEOUT_SEC)


def run_claude_code(
    container_id: str,
    instruction: str,
    system_prompt: str,
    model: str,
    max_turns: int,
    timeout: float,
    oauth_token: str,
) -> subprocess.CompletedProcess[str]:
    _write_file_to_container(container_id, instruction, "/tmp/instruction.txt")
    _write_file_to_container(container_id, system_prompt, "/tmp/system_prompt.txt")

    claude_cmd = (
        f'claude --verbose -p "$(cat /tmp/instruction.txt)"'
        f' --append-system-prompt "$(cat /tmp/system_prompt.txt)"'
        f" --permission-mode bypassPermissions --output-format stream-json"
        f" --max-turns {max_turns} --model {model}"
    )

    cmd: list[str] = ["docker", "exec"]
    cmd += ["-e", f"CLAUDE_CODE_OAUTH_TOKEN={oauth_token}"]
    cmd += ["-e", "DEBIAN_FRONTEND=noninteractive"]
    cmd += ["-w", CONTAINER_WORKDIR]
    cmd += [container_id, "bash", "-c", claude_cmd]

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_verifier(container_id: str, timeout: float) -> subprocess.CompletedProcess[str]:
    return docker_exec(
        container_id,
        [
            "bash",
            "-c",
            f"chmod +x {CONTAINER_TESTS_DIR}/test.sh && bash {CONTAINER_TESTS_DIR}/test.sh",
        ],
        timeout=timeout,
        env={"DEBIAN_FRONTEND": "noninteractive"},
    )


def extract_reward(container_id: str) -> float:
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            reward_local = Path(tmp_dir) / "reward.txt"
            docker_cp_from_container(container_id, REWARD_FILE_PATH, reward_local)
            return float(reward_local.read_text().strip())
    except subprocess.CalledProcessError:
        return 0.0
    except ValueError:
        return 0.0


def _get_timeouts(task_config: dict, timeout_multiplier: float) -> tuple[float, float]:
    agent_timeout = float(
        task_config.get("agent", {}).get("timeout_sec", DEFAULT_AGENT_TIMEOUT_SEC)
    )
    verifier_timeout = float(
        task_config.get("verifier", {}).get("timeout_sec", DEFAULT_VERIFIER_TIMEOUT_SEC)
    )
    return agent_timeout * timeout_multiplier, verifier_timeout * timeout_multiplier


def run_single_task(
    task_name: str,
    task_dir: Path,
    fork_config: tuple[str, int, str],
    oauth_token: str,
    timeout_multiplier: float,
    results_dir: Path,
) -> dict:
    model, max_turns, system_prompt = fork_config
    task_config = load_task_config(task_dir)
    agent_timeout, verifier_timeout = _get_timeouts(task_config, timeout_multiplier)

    result: dict = {
        "challenge": task_name,
        "mode": "autofyn-local",
        "image": f"tb2-{task_name}",
        "passed": False,
        "reward": None,
        "error": None,
        "solve_stdout": None,
        "solve_stderr": None,
        "verify_stdout": None,
        "verify_stderr": None,
    }

    container_id: str | None = None
    try:
        print(f"  Building image for {task_name}...")
        image = build_task_image(task_dir, task_name)
        result["image"] = image

        print(f"  Starting container from {image}...")
        container_id = start_container(image)
        setup_container_dirs(container_id)

        instruction = (task_dir / "instruction.md").read_text()

        print(f"  Running Claude Code (timeout={agent_timeout}s)...")
        solve_proc = run_claude_code(
            container_id, instruction, system_prompt, model, max_turns, agent_timeout, oauth_token
        )
        result["solve_stdout"] = solve_proc.stdout[-STDOUT_TRUNCATE_LEN:] if solve_proc.stdout else ""
        result["solve_stderr"] = solve_proc.stderr[-STDERR_TRUNCATE_LEN:] if solve_proc.stderr else ""

        copy_test_files(container_id, task_dir)

        print(f"  Running verifier (timeout={verifier_timeout}s)...")
        verify_proc = run_verifier(container_id, verifier_timeout)
        result["verify_stdout"] = verify_proc.stdout[-STDOUT_TRUNCATE_LEN:] if verify_proc.stdout else ""
        result["verify_stderr"] = verify_proc.stderr[-STDERR_TRUNCATE_LEN:] if verify_proc.stderr else ""

        reward = extract_reward(container_id)
        result["reward"] = reward
        result["passed"] = reward >= 1.0

    except subprocess.TimeoutExpired as exc:
        result["error"] = f"Timeout: {exc}"
        print(f"  TIMEOUT: {exc}")
    except subprocess.CalledProcessError as exc:
        result["error"] = f"Command failed (rc={exc.returncode}): {exc.stderr}"
        print(f"  ERROR: {exc}")
    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ERROR: {exc}")
    finally:
        if container_id:
            print(f"  Stopping container {container_id[:12]}...")
            stop_container(container_id)

    results_dir.mkdir(parents=True, exist_ok=True)
    result_file = results_dir / f"{task_name}.json"
    result_file.write_text(json.dumps(result, indent=2))
    return result


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def print_summary(results: list[dict]) -> None:
    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    print(f"{'Task':<30} {'Reward':>8} {'Baseline':>10} {'Delta':>8} {'Status':<8}")
    print("-" * 70)
    for result in results:
        task = result["challenge"]
        reward_val: float = result["reward"] if result["reward"] is not None else 0.0
        baseline = BASELINE_REWARDS.get(task, 0.0)
        status = "PASS" if result["passed"] else "FAIL"
        row = f"{task:<30} {_fmt_pct(reward_val):>8} {_fmt_pct(baseline):>10} {f'{(reward_val - baseline) * 100:+.1f}%':>8} {status:<8}"
        print(row)
    print("-" * 70)


def main() -> None:
    args = parse_args()
    oauth_token = validate_environment()

    fork_dir_arg: str = args.fork_dir
    fork_dir = (REPO_DIR / fork_dir_arg).resolve()
    fork_config = load_fork_config(fork_dir)

    task_names: list[str] = [t.strip() for t in args.tasks.split(",") if t.strip()]
    timeout_multiplier: float = args.timeout_multiplier

    results_dir = JOBS_DIR / "local-experiment"
    all_results: list[dict] = []

    for task_name in task_names:
        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        print("=" * 60)

        task_dir = TASKS_DIR / task_name
        if not task_dir.exists():
            print(f"  ERROR: Task directory not found: {task_dir}")
            error_result: dict = {
                "challenge": task_name,
                "mode": "autofyn-local",
                "passed": False,
                "reward": None,
                "error": f"Task directory not found: {task_dir}",
            }
            all_results.append(error_result)
            continue

        all_results.append(
            run_single_task(task_name, task_dir, fork_config, oauth_token, timeout_multiplier, results_dir)
        )

    print_summary(all_results)
    print(f"Results saved to: {results_dir}")


if __name__ == "__main__":
    main()
