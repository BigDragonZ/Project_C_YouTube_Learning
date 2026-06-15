#!/bin/bash
# Auto-restart batch script that runs until all files are processed
# Usage: nohup ./auto_batch_anki.sh >> /tmp/auto_batch.log 2>&1 &

cd "$(dirname "$0")"

iteration=0
while true; do
    iteration=$((iteration + 1))
    echo "=== Iteration $iteration at $(date) ===" >> /tmp/auto_batch.log
    
    # Run the batch script with unbuffered output
    stdbuf -oL -eL uv run python -u batch_generate_anki.py >> /tmp/auto_batch.log 2>&1
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo "[COMPLETE] All files processed successfully at $(date)" >> /tmp/auto_batch.log
        break
    else
        echo "[RESTART] Exit code $exit_code, restarting in 10s..." >> /tmp/auto_batch.log
        sleep 10
    fi
done
