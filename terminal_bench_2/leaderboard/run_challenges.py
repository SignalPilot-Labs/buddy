#!/usr/bin/env python3
"""Run terminal-bench-2 challenges locally in Docker containers.

Modes:
  oracle      - runs solution/solve.sh from the challenge
  claude-code - runs Claude Code CLI inside the container to solve the challenge

Usage:
  python3 run_challenges.py --mode oracle --challenges caffe-cifar-10,dna-assembly
  python3 run_challenges.py --mode claude-code
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path


DATASET_DIR = Path("/tmp/tb2-dataset")
RESULTS_DIR = Path("/tmp/bench-results")

DEFAULT_CHALLENGES = [
    "caffe-cifar-10",
    "dna-assembly",
    "dna-insert",
    "filter-js-from-html",
    "fix-code-vulnerability",
    "install-windows-3.11",
    "make-doom-for-mips",
    "raman-fitting",
    "train-fasttext",
]

PLATFORM = "linux/amd64"
CONTAINER_WORKDIR = "/app"
CONTAINER_LOGS_DIR = "/logs"
CONTAINER_VERIFIER_DIR = "/logs/verifier"
CONTAINER_AGENT_DIR = "/logs/agent"
CONTAINER_TESTS_DIR = "/tests"
CONTAINER_SOLUTION_DIR = "/solution"
REWARD_FILE_PATH = "/logs/verifier/reward.txt"

NODE_INSTALL_COMMANDS = (
    "apt-get update -qq && apt-get install -y -qq curl sudo "
    "&& curl -fsSL https://deb.nodesource.com/setup_20.x | bash - "
    "&& apt-get install -y -qq nodejs "
    "&& npm install -g @anthropic-ai/claude-code "
    "&& (id -u agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent) "
    "&& echo 'agent ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers "
    "&& cp -r /app /home/agent/app 2>/dev/null || true "
    "&& chown -R agent:agent /home/agent/app 2>/dev/null || true "
    "&& chown -R agent:agent /app 2>/dev/null || true"
)


def load_task_config(challenge_dir: Path) -> dict:
    task_toml_path = challenge_dir / "task.toml"
    with open(task_toml_path, "rb") as f:
        return tomllib.load(f)


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
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec"]
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
        [
            "mkdir",
            "-p",
            CONTAINER_AGENT_DIR,
            CONTAINER_VERIFIER_DIR,
            CONTAINER_TESTS_DIR,
            CONTAINER_SOLUTION_DIR,
        ],
        timeout=30.0,
    )


def copy_test_files(container_id: str, challenge_dir: Path) -> None:
    tests_dir = challenge_dir / "tests"
    # Copy all files in the tests directory
    for test_file in tests_dir.iterdir():
        if test_file.is_file():
            docker_cp_to_container(
                test_file, container_id, CONTAINER_TESTS_DIR + "/" + test_file.name
            )


def run_verifier(container_id: str, verifier_timeout: float) -> subprocess.CompletedProcess:
    return docker_exec(
        container_id,
        [
            "bash",
            "-c",
            f"chmod +x {CONTAINER_TESTS_DIR}/test.sh && bash {CONTAINER_TESTS_DIR}/test.sh",
        ],
        timeout=verifier_timeout,
        env={"DEBIAN_FRONTEND": "noninteractive"},
    )


def extract_reward(container_id: str) -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        reward_local = Path(tmp_dir) / "reward.txt"
        docker_cp_from_container(container_id, REWARD_FILE_PATH, reward_local)
        reward_text = reward_local.read_text().strip()
        return int(reward_text)


def run_oracle_solve(
    container_id: str, challenge_dir: Path, agent_timeout: float
) -> subprocess.CompletedProcess:
    solve_sh = challenge_dir / "solution" / "solve.sh"
    docker_cp_to_container(
        solve_sh, container_id, CONTAINER_SOLUTION_DIR + "/solve.sh"
    )
    return docker_exec(
        container_id,
        [
            "bash",
            "-c",
            f"chmod +x {CONTAINER_SOLUTION_DIR}/solve.sh && bash {CONTAINER_SOLUTION_DIR}/solve.sh",
        ],
        timeout=agent_timeout,
        env={"DEBIAN_FRONTEND": "noninteractive"},
    )


def install_claude_code(container_id: str) -> subprocess.CompletedProcess:
    return docker_exec(
        container_id,
        ["bash", "-c", NODE_INSTALL_COMMANDS],
        timeout=600.0,
        env={"DEBIAN_FRONTEND": "noninteractive"},
    )


def run_claude_code_solve(
    container_id: str,
    instruction: str,
    agent_timeout: float,
    oauth_token: str,
) -> subprocess.CompletedProcess:
    # Write instruction to file to avoid shell escaping issues
    write_cmd = ["docker", "exec", container_id, "bash", "-c",
                 f"cat > /tmp/instruction.txt << 'INSTRUCTION_EOF'\n{instruction}\nINSTRUCTION_EOF"]
    subprocess.run(write_cmd, capture_output=True, text=True, timeout=30.0)

    # Run claude as non-root 'agent' user from /app
    cmd = ["docker", "exec"]
    cmd += ["-e", f"CLAUDE_CODE_OAUTH_TOKEN={oauth_token}"]
    cmd += ["-e", "DEBIAN_FRONTEND=noninteractive"]
    cmd += ["-e", "HOME=/home/agent"]
    cmd += ["-u", "agent"]
    cmd += ["-w", "/app"]
    cmd += [container_id, "bash", "-c",
            'claude --dangerously-skip-permissions -p "$(cat /tmp/instruction.txt)"']
    return subprocess.run(cmd, capture_output=True, text=True, timeout=agent_timeout)


def run_oracle_challenge(
    challenge_name: str,
    challenge_dir: Path,
    task_config: dict,
    results_path: Path,
) -> dict:
    agent_timeout: float = task_config["agent"]["timeout_sec"]
    verifier_timeout: float = task_config["verifier"]["timeout_sec"]
    docker_image: str = task_config["environment"]["docker_image"]

    result: dict = {
        "challenge": challenge_name,
        "mode": "oracle",
        "image": docker_image,
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
        print(f"  Starting container from {docker_image}...")
        container_id = start_container(docker_image)
        setup_container_dirs(container_id)

        print(f"  Running oracle solve (timeout={agent_timeout}s)...")
        solve_proc = run_oracle_solve(container_id, challenge_dir, agent_timeout)
        result["solve_stdout"] = solve_proc.stdout[-5000:] if solve_proc.stdout else ""
        result["solve_stderr"] = solve_proc.stderr[-5000:] if solve_proc.stderr else ""

        copy_test_files(container_id, challenge_dir)

        print(f"  Running verifier (timeout={verifier_timeout}s)...")
        verify_proc = run_verifier(container_id, verifier_timeout)
        result["verify_stdout"] = verify_proc.stdout[-5000:] if verify_proc.stdout else ""
        result["verify_stderr"] = verify_proc.stderr[-5000:] if verify_proc.stderr else ""

        reward = extract_reward(container_id)
        result["reward"] = reward
        result["passed"] = reward == 1

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

    result_file = results_path / f"{challenge_name}.json"
    result_file.write_text(json.dumps(result, indent=2))
    return result


def run_claude_code_challenge(
    challenge_name: str,
    challenge_dir: Path,
    task_config: dict,
    results_path: Path,
    oauth_token: str,
) -> dict:
    agent_timeout: float = task_config["agent"]["timeout_sec"]
    verifier_timeout: float = task_config["verifier"]["timeout_sec"]
    docker_image: str = task_config["environment"]["docker_image"]

    result: dict = {
        "challenge": challenge_name,
        "mode": "claude-code",
        "image": docker_image,
        "passed": False,
        "reward": None,
        "error": None,
        "install_stdout": None,
        "install_stderr": None,
        "solve_stdout": None,
        "solve_stderr": None,
        "verify_stdout": None,
        "verify_stderr": None,
    }

    container_id: str | None = None
    try:
        print(f"  Starting container from {docker_image}...")
        container_id = start_container(docker_image)
        setup_container_dirs(container_id)

        print("  Installing Node.js and Claude Code CLI...")
        install_proc = install_claude_code(container_id)
        result["install_stdout"] = install_proc.stdout[-3000:] if install_proc.stdout else ""
        result["install_stderr"] = install_proc.stderr[-3000:] if install_proc.stderr else ""
        if install_proc.returncode != 0:
            raise RuntimeError(
                f"Claude Code installation failed (rc={install_proc.returncode})"
            )

        instruction_path = challenge_dir / "instruction.md"
        instruction = instruction_path.read_text()

        print(f"  Running Claude Code (timeout={agent_timeout}s)...")
        solve_proc = run_claude_code_solve(
            container_id, instruction, agent_timeout, oauth_token
        )
        result["solve_stdout"] = solve_proc.stdout[-10000:] if solve_proc.stdout else ""
        result["solve_stderr"] = solve_proc.stderr[-5000:] if solve_proc.stderr else ""

        copy_test_files(container_id, challenge_dir)

        print(f"  Running verifier (timeout={verifier_timeout}s)...")
        verify_proc = run_verifier(container_id, verifier_timeout)
        result["verify_stdout"] = verify_proc.stdout[-5000:] if verify_proc.stdout else ""
        result["verify_stderr"] = verify_proc.stderr[-5000:] if verify_proc.stderr else ""

        reward = extract_reward(container_id)
        result["reward"] = reward
        result["passed"] = reward == 1

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

    result_file = results_path / f"{challenge_name}.json"
    result_file.write_text(json.dumps(result, indent=2))
    return result


def print_challenge_result(result: dict) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    error_suffix = f" | error: {result['error']}" if result["error"] else ""
    reward_str = f" (reward={result['reward']})" if result["reward"] is not None else ""
    print(f"  [{status}] {result['challenge']}{reward_str}{error_suffix}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run terminal-bench-2 challenges in Docker containers."
    )
    parser.add_argument(
        "--mode",
        choices=["oracle", "claude-code"],
        required=True,
        help="Solve mode: oracle (use provided solution) or claude-code (use Claude Code CLI)",
    )
    parser.add_argument(
        "--challenges",
        default=",".join(DEFAULT_CHALLENGES),
        help="Comma-separated list of challenge names (default: all 9)",
    )
    parser.add_argument(
        "--timeout-multiplier",
        type=float,
        default=1.0,
        help="Multiplier for agent and verifier timeouts (default: 1.0)",
    )
    return parser.parse_args()


def validate_claude_code_env() -> str:
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "")
    if not token:
        print("ERROR: CLAUDE_CODE_OAUTH_TOKEN environment variable is not set.")
        sys.exit(1)
    return token


def main() -> None:
    args = parse_args()
    mode: str = args.mode
    challenges: list[str] = [c.strip() for c in args.challenges.split(",") if c.strip()]

    timeout_multiplier: float = args.timeout_multiplier

    oauth_token = ""
    if mode == "claude-code":
        oauth_token = validate_claude_code_env()

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_path = RESULTS_DIR / timestamp
    results_path.mkdir(parents=True, exist_ok=True)
    print(f"Results will be saved to {results_path}")

    all_results: list[dict] = []

    for challenge_name in challenges:
        print(f"\n{'='*60}")
        print(f"Challenge: {challenge_name} | Mode: {mode}")
        print("=" * 60)

        challenge_dir = DATASET_DIR / challenge_name
        if not challenge_dir.exists():
            print(f"  ERROR: Challenge directory not found: {challenge_dir}")
            error_result: dict = {
                "challenge": challenge_name,
                "mode": mode,
                "passed": False,
                "reward": None,
                "error": f"Challenge directory not found: {challenge_dir}",
            }
            all_results.append(error_result)
            (results_path / f"{challenge_name}.json").write_text(
                json.dumps(error_result, indent=2)
            )
            continue

        task_config = load_task_config(challenge_dir)

        # Apply timeout multiplier
        task_config["agent"]["timeout_sec"] *= timeout_multiplier
        task_config["verifier"]["timeout_sec"] *= timeout_multiplier

        if mode == "oracle":
            result = run_oracle_challenge(
                challenge_name, challenge_dir, task_config, results_path
            )
        else:
            result = run_claude_code_challenge(
                challenge_name, challenge_dir, task_config, results_path, oauth_token
            )

        all_results.append(result)
        print_challenge_result(result)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in all_results if r["passed"])
    total = len(all_results)
    for result in all_results:
        print_challenge_result(result)
    print(f"\n{passed}/{total} passed")
    print(f"Results saved to: {results_path}")


if __name__ == "__main__":
    main()
