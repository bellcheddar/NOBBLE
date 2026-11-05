#!/usr/bin/env bash
# The newest *complete* campaign with a given prefix, in one place (F189).
#
# Complete means it wrote `campaign.json`, which every assembler writes last.
# `ls -d campaigns/<prefix>_* | tail -1` names the newest directory instead,
# and a failed assembly leaves one holding an empty `yaml/` and an empty
# `outputs/`: three of those sat in `campaigns/` from a failing design scan,
# and the newest of them was what the chain would have handed to
# `run_design.sh` (F57).
#
# That was fixed in `run_chain.sh` and nowhere else. `refresh.sh`,
# `run_corrected.sh` and `run_design.sh` all still used the naive form, which
# is F57's lesson learned in one file out of four. The Python side has the
# same rule in `campaign.latest()`, and this is it in the other language,
# sourced rather than copied so there is one definition per language rather
# than one per script.
#
# Sourced, like `tools/wait_for_gpu.sh`:
#
#   source "$ROOT/tools/newest_complete.sh"
#   CAMPAIGN="$(nobble_newest_complete corrected)"
#
# Prints nothing and returns 1 when no complete campaign has that prefix, so
# a caller can tell "none" from "the newest one" without parsing a message.

nobble_newest_complete() {
  local prefix="$1" directory found=""
  for directory in campaigns/"$prefix"_*; do
    # The glob itself when nothing matches, which is a directory that does
    # not exist rather than a campaign.
    [[ -d "$directory" ]] || continue
    [[ -f "$directory/campaign.json" ]] && found="$found$directory"$'\n'
  done
  [[ -n "$found" ]] || return 1
  printf '%s\n' "$found" | sed '/^$/d' | sort | tail -1
}
