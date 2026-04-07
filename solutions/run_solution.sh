#!/bin/bash
# Run a solution script against a challenge container
# Usage: ./run_solution.sh <challenge-name> <solve-script>

set -e

CHALLENGE=$1
SOLVE_SCRIPT=$2
DATASET_DIR="/tmp/tb2-dataset"
CHALLENGE_DIR="$DATASET_DIR/$CHALLENGE"

if [ -z "$CHALLENGE" ] || [ -z "$SOLVE_SCRIPT" ]; then
    echo "Usage: $0 <challenge-name> <solve-script>"
    exit 1
fi

# Load docker image from task.toml
DOCKER_IMAGE=$(python3 -c "
import tomllib
with open('$CHALLENGE_DIR/task.toml', 'rb') as f:
    config = tomllib.load(f)
print(config['environment']['docker_image'])
")

AGENT_TIMEOUT=$(python3 -c "
import tomllib
with open('$CHALLENGE_DIR/task.toml', 'rb') as f:
    config = tomllib.load(f)
print(int(config['agent']['timeout_sec']))
")

VERIFIER_TIMEOUT=$(python3 -c "
import tomllib
with open('$CHALLENGE_DIR/task.toml', 'rb') as f:
    config = tomllib.load(f)
print(int(config['verifier']['timeout_sec']))
")

echo "=== Challenge: $CHALLENGE ==="
echo "Image: $DOCKER_IMAGE"
echo "Agent timeout: ${AGENT_TIMEOUT}s"
echo "Verifier timeout: ${VERIFIER_TIMEOUT}s"

# Start container
echo "Starting container..."
CONTAINER_ID=$(docker run -d --platform linux/amd64 "$DOCKER_IMAGE" sleep infinity)
echo "Container: ${CONTAINER_ID:0:12}"

cleanup() {
    echo "Stopping container ${CONTAINER_ID:0:12}..."
    docker rm -f "$CONTAINER_ID" > /dev/null 2>&1
}
trap cleanup EXIT

# Setup dirs
docker exec "$CONTAINER_ID" mkdir -p /logs/agent /logs/verifier /tests /solution

# Copy and run solution
docker cp "$SOLVE_SCRIPT" "$CONTAINER_ID:/solution/solve.sh"
echo "Running solution..."
docker exec -e DEBIAN_FRONTEND=noninteractive "$CONTAINER_ID" bash -c \
    "chmod +x /solution/solve.sh && bash /solution/solve.sh" 2>&1 | tail -50
SOLVE_RC=$?
echo "Solution exit code: $SOLVE_RC"

# Copy test files
for f in "$CHALLENGE_DIR/tests/"*; do
    if [ -f "$f" ]; then
        docker cp "$f" "$CONTAINER_ID:/tests/$(basename $f)"
    fi
done

# Run verifier
echo "Running verifier..."
docker exec -e DEBIAN_FRONTEND=noninteractive "$CONTAINER_ID" bash -c \
    "chmod +x /tests/test.sh && bash /tests/test.sh" 2>&1 | tail -80
VERIFY_RC=$?

# Extract reward
REWARD=$(docker exec "$CONTAINER_ID" cat /logs/verifier/reward.txt 2>/dev/null || echo "N/A")
echo ""
echo "=== RESULT: $CHALLENGE ==="
echo "Reward: $REWARD"
if [ "$REWARD" = "1" ]; then
    echo "STATUS: PASS"
else
    echo "STATUS: FAIL"
fi
