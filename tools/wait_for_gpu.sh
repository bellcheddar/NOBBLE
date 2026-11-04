#!/usr/bin/env bash
# Block until no NOBBLE campaign is using the MPS device.
#
# Sourced by every script that starts inference. There is one GPU, so two
# campaigns sharing it halve each other's throughput and risk an
# out-of-memory on the larger jobs. This lived as a copied loop in two
# scripts and was missing from a third, and the list of sessions had already
# drifted: run_design.sh waited for a session named nobble-campaign that
# nothing creates, while the chain actually runs in nobble-chain.
#
# One list, one place to add to it.
NOBBLE_GPU_SESSIONS=(nobble-bench nobble-corrected nobble-chain nobble-campaign nobble-design nobble-tier2)

nobble_wait_for_gpu() {
  local session
  for session in "${NOBBLE_GPU_SESSIONS[@]}"; do
    # Never wait on the session this script is itself running inside.
    if [[ "${TMUX_PANE:-}" != "" ]] && \
       [[ "$(tmux display-message -p '#S' 2>/dev/null)" == "$session" ]]; then
      continue
    fi
    if tmux has-session -t "$session" 2>/dev/null; then
      echo "=== waiting for $session to release the GPU $(date -u +%H:%M:%SZ) ==="
      while tmux has-session -t "$session" 2>/dev/null; do sleep 60; done
    fi
  done
}
