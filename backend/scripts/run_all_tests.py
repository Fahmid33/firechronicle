"""Consolidated Test Runner for FireChronicle Pará (BR-PA) Backend.

Executes:
1. Pytest integration & contract suite (tests/test_api_v1.py)
2. End-to-end FastAPI TestClient smoke test (scripts/run_smoke_test.py)
3. Canonical 2012 sparse-to-dense constraint verifier (verify.py)

Prints a structured consolidated test report and exits non-zero if any stage fails.
"""

from pathlib import Path
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run_stage(label: str, cmd: list[str]) -> bool:
    print(f"\n=== [{label}] ===")
    print("Command:", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=False)
    ok = proc.returncode == 0
    print(f"Result [{label}]: {'PASSED' if ok else 'FAILED'} (exit={proc.returncode})")
    return ok


def main() -> int:
    stages = [
        ("Pytest Integration Suite", [PYTHON, "-m", "pytest", "-v", "tests/test_api_v1.py"]),
        ("API Smoke Test Runner", [PYTHON, "-u", "scripts/run_smoke_test.py"]),
        ("2012 Canonical Dense-Grid Verifier", [PYTHON, "-u", "verify.py"]),
    ]

    results = []
    for label, cmd in stages:
        results.append((label, run_stage(label, cmd)))

    print("\n============================================================")
    print("FIRECHRONICLE BACKEND CONSOLIDATED TEST REPORT")
    print("============================================================")
    all_ok = True
    for label, ok in results:
        status_str = "PASS" if ok else "FAIL"
        print(f"  - {label}: {status_str}")
        if not ok:
            all_ok = False
    print("============================================================")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
