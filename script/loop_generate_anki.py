#!/usr/bin/env python3
"""
Loop wrapper for batch_generate_anki.py that auto-restarts until all files are processed.
Runs indefinitely with no timeout - designed for background execution.
"""

import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

def main():
    iteration = 0
    while True:
        iteration += 1
        print(f"=== Iteration {iteration} ===", flush=True)
        
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "batch_generate_anki.py")],
                capture_output=False,  # Stream output directly
                text=True,
                timeout=None  # No timeout - run until completion
            )
            
            # If script completed successfully, we're done
            if result.returncode == 0:
                print("\n[COMPLETE] All files processed!")
                break
            else:
                print(f"[RESTART] Script exited with code {result.returncode}, restarting...", flush=True)
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n[INTERRUPTED] Stopping...")
            break
        except Exception as e:
            print(f"[ERROR] {e}, restarting in 5s...", flush=True)
            time.sleep(5)
            continue

if __name__ == "__main__":
    main()
