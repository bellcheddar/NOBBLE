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

# How long between checks. A minute is right for a run measured in hours,
# and is far too long for a test to sit through: without a way to shorten
# it, nothing could assert that this waits at all, and removing the wait
# entirely went unnoticed by seven tests.
NOBBLE_GPU_POLL_SECONDS="${NOBBLE_GPU_POLL_SECONDS:-60}"

# What a run on the device looks like in ps. Overridable for the same
# reason as the interval: on a machine with a campaign already going, a
# test of whether this waits can only be about its own fake process, and
# the alternative is a test that skips itself exactly when it matters.
NOBBLE_GPU_PATTERN="${NOBBLE_GPU_PATTERN:-nobble\.execute\.runner}"

# The processes that actually hold the device, which is what the sessions
# were standing in for. A tmux session name is a proxy: kill a chain and its
# run_queue child keeps running, outside any session this list knows, and a
# second campaign would have started on the same GPU with this returning
# immediately. Asking for the runner itself cannot be wrong about that.
#
# Ancestors are excluded so a script running inside a campaign never waits
# for the campaign that launched it, which would deadlock rather than
# protect anything. On this platform that is a second line of defence
# rather than the working mechanism: macOS `pgrep -f` already omits its own
# ancestry, parent and grandparent alike, while reporting siblings. Kept
# because the exclusion is what makes the guard correct rather than
# accidentally correct, and said plainly here because a test cannot
# demonstrate it while pgrep behaves this way (F60).
nobble_ancestor_pids() {
  local pid=$$ chain=""
  while [[ -n "$pid" && "$pid" != "0" && "$pid" != "1" ]]; do
    chain="$chain $pid"
    pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
  done
  echo "$chain"
}

nobble_gpu_pids() {
  local ancestors=" $(nobble_ancestor_pids) " pid command
  for pid in $(pgrep -f "$NOBBLE_GPU_PATTERN" 2>/dev/null); do
    [[ "$ancestors" == *" $pid "* ]] && continue
    command="$(ps -o command= -p "$pid" 2>/dev/null)"
    # `--throughput` rewrites throughput.json from results already on disk
    # and never opens the device. refresh.sh runs it after every campaign,
    # so a run that is only measuring must not look like one that is
    # inferring, or the chain would wait 60 seconds on its own bookkeeping.
    [[ "$command" == *"--throughput"* ]] && continue
    echo "$pid"
  done
}

# The two halves are separate functions because they fail independently and
# are checked independently: with a campaign in a tmux session on this
# machine, the session loop never returns, so a test of whether the process
# wait waits can only reach it directly.
nobble_wait_for_runners() {
  local pids
  pids="$(nobble_gpu_pids)"
  if [[ -n "$pids" ]]; then
    echo "=== waiting for runner $(echo "$pids" | tr "\n" " ")to release the" \
         "GPU $(date -u +%H:%M:%SZ) ==="
    while [[ -n "$(nobble_gpu_pids)" ]]; do sleep "$NOBBLE_GPU_POLL_SECONDS"; done
  fi
}

nobble_wait_for_sessions() {
  local session
  for session in "${NOBBLE_GPU_SESSIONS[@]}"; do
    # Never wait on the session this script is itself running inside.
    if [[ "${TMUX_PANE:-}" != "" ]] && \
       [[ "$(tmux display-message -p '#S' 2>/dev/null)" == "$session" ]]; then
      continue
    fi
    if tmux has-session -t "$session" 2>/dev/null; then
      echo "=== waiting for $session to release the GPU $(date -u +%H:%M:%SZ) ==="
      while tmux has-session -t "$session" 2>/dev/null; do sleep "$NOBBLE_GPU_POLL_SECONDS"; done
    fi
  done
}

nobble_wait_for_gpu() {
  nobble_wait_for_sessions
  # Then whatever is on the device regardless of where it was started from.
  nobble_wait_for_runners
}
