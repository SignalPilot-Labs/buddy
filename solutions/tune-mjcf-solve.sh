#!/bin/bash
set -e

# The task: produce /app/model.xml that simulates 60% or less of reference time
# while matching final physics state within atol=1e-5.
#
# Approach:
#   The reference model is a 41-element elastic cable with damped joints.
#   The system is well-damped (joint damping=0.015, slider damping=0.1).
#   The elasticity cable plugin uses a stiff implicit formulation internally.
#
# Key insight from test: "potentially different timesteps" are OK as long as
# final states match within atol=1e-5.
#
# Optimizations applied (without changing physical body properties):
#   1. Switch integrator to 'implicitfast' — A-stable, handles stiff elasticity
#      better, allows larger timesteps without numerical blowup
#   2. Increase timestep from default 0.002 to 0.004 — 2x fewer steps
#   3. Reduce solver iterations: Newton solver with fewer iterations
#
# For a well-damped cable, doubling the timestep with implicitfast should
# produce final states within 1e-5 of the reference Euler trajectory at t=2s,
# because:
#   - The cable is heavily damped and reaches near-equilibrium quickly
#   - implicitfast is more accurate per step than Euler at larger timesteps
#   - The final state at t=2s is close to a fixed point of the dynamics
#
# If strict accuracy is needed, we can fall back to solver-only tuning.

python3 - << 'PYEOF'
import xml.etree.ElementTree as ET
import mujoco
import numpy as np
import time
from pathlib import Path

ref_path = Path("/app/model_ref.xml")
out_path = Path("/app/model.xml")

TOTAL_SIM_TIME = 2.0
ATOL = 1e-5
TARGET_PCT = 0.6

def simulate_model(model, seed):
    """Simulate model with randomized initial qpos and return final state."""
    data = mujoco.MjData(model)
    nstep = int(TOTAL_SIM_TIME / model.opt.timestep)
    rng = np.random.default_rng(seed)
    data.qpos += rng.normal(0, 0.01, size=data.qpos.shape)
    mujoco.mj_forward(model, data)
    for _ in range(nstep):
        mujoco.mj_step(model, data)
    full_physics = mujoco.mjtState.mjSTATE_FULLPHYSICS
    state = np.zeros(mujoco.mj_stateSize(model, full_physics))
    mujoco.mj_getState(model, data, state, full_physics)
    return state

def measure_time(model, n_runs=5):
    """Measure average simulation time."""
    times = []
    for _ in range(n_runs):
        seed = np.random.randint(0, 10000)
        t0 = time.perf_counter()
        simulate_model(model, seed)
        times.append(time.perf_counter() - t0)
    return np.mean(times)

def check_correctness(model, model_ref):
    """Check that final states match within atol for multiple seeds."""
    max_diff = 0.0
    for seed in [42, 123, 999]:
        state = simulate_model(model, seed)
        state_ref = simulate_model(model_ref, seed)
        diff = np.linalg.norm(state - state_ref)
        max_diff = max(max_diff, diff)
        if not np.allclose(state, state_ref, atol=ATOL):
            return False, max_diff
    return True, max_diff

def write_model(timestep, integrator, solver, iterations, tolerance, ls_iterations):
    """Write model.xml with given parameters."""
    tree = ET.parse(ref_path)
    root = tree.getroot()
    option = root.find("option")
    if option is None:
        option = ET.Element("option")
        insert_idx = 0
        known_before = {"extension", "statistic", "visual", "compiler", "size"}
        for i, child in enumerate(root):
            if child.tag in known_before:
                insert_idx = i + 1
        root.insert(insert_idx, option)
    option.set("timestep", str(timestep))
    option.set("integrator", integrator)
    option.set("solver", solver)
    option.set("iterations", str(iterations))
    option.set("tolerance", str(tolerance))
    option.set("ls_iterations", str(ls_iterations))
    tree.write(out_path, encoding="unicode", xml_declaration=False)
    return mujoco.MjModel.from_xml_path(str(out_path))

model_ref = mujoco.MjModel.from_xml_path(str(ref_path))
print(f"Reference model: timestep={model_ref.opt.timestep}, integrator={model_ref.opt.integrator}")

# Measure reference timing
t_ref = measure_time(model_ref, n_runs=5)
print(f"Reference time: {t_ref:.4f}s")
target_time = t_ref * TARGET_PCT
print(f"Target time: {target_time:.4f}s")

# Candidates to try, ordered by expected speedup
# Each entry: (timestep, integrator, solver, iterations, tolerance, ls_iterations)
candidates = [
    # Primary strategy: implicitfast + 2x timestep + Newton solver
    (0.004, "implicitfast", "Newton", 10, 1e-9, 5),
    # More aggressive: 3x timestep
    (0.006, "implicitfast", "Newton", 10, 1e-9, 5),
    # Conservative: same timestep, just solver tuning
    (0.002, "implicitfast", "Newton", 10, 1e-9, 5),
    # Only solver reduction, no integrator change
    (0.002, "Euler", "Newton", 10, 1e-9, 5),
    # Euler with 2x timestep
    (0.004, "Euler", "Newton", 10, 1e-9, 5),
]

best_params = None
best_time = float("inf")

for params in candidates:
    timestep, integrator, solver, iterations, tolerance, ls_iters = params
    try:
        model = write_model(timestep, integrator, solver, iterations, tolerance, ls_iters)
    except Exception as e:
        print(f"Failed to load model with params {params}: {e}")
        continue

    # Quick correctness check
    correct, diff = check_correctness(model, model_ref)
    if not correct:
        print(f"params={params}: FAILED correctness (diff={diff:.2e})")
        continue

    t_model = measure_time(model, n_runs=5)
    pct = t_model / t_ref
    print(f"params={params}: time={t_model:.4f}s ({pct*100:.1f}% of ref), diff={diff:.2e}")

    if pct <= TARGET_PCT and t_model < best_time:
        best_time = t_model
        best_params = params

if best_params is not None:
    print(f"\nBest params: {best_params}")
    write_model(*best_params)
    print(f"Written to {out_path}")
else:
    print("\nNo candidate passed both correctness and speed. Using best solver-only tuning.")
    # Fallback: Newton solver only, same timestep — guaranteed correct
    fallback = (0.002, "Euler", "Newton", 15, 1e-9, 5)
    write_model(*fallback)
    t_fallback = measure_time(mujoco.MjModel.from_xml_path(str(out_path)), n_runs=5)
    print(f"Fallback time: {t_fallback:.4f}s ({t_fallback/t_ref*100:.1f}% of ref)")
    print(f"Written fallback to {out_path}")

# Final verification
model_final = mujoco.MjModel.from_xml_path(str(out_path))
correct, diff = check_correctness(model_final, model_ref)
t_final = measure_time(model_final, n_runs=5)
print(f"\nFinal model: correct={correct}, diff={diff:.2e}, time={t_final:.4f}s ({t_final/t_ref*100:.1f}% of ref)")
PYEOF

echo "Solution complete: /app/model.xml written"
