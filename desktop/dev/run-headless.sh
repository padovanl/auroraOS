#!/bin/bash
# Host entry point for headless desktop tests.
# Usage: desktop/dev/run-headless.sh [scenario.sh] [output_dir]
# The scenario runs inside the session after the shell has started.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
scenario="${1:-}"
out="${2:-$repo/work/dev-out}"
mkdir -p "$out" "$repo/work/dev-cache"

docker build -q -t aurora-os-dev "$repo/desktop/dev" >/dev/null

args=(--rm -v "$repo:/src:ro" -v "$out:/out" -v "$repo/work/dev-cache:/cache")
inner_scenario=""
if [ -n "$scenario" ]; then
    # Copy next to the output: the docker daemon may not see private tmp dirs.
    cp "$scenario" "$out/scenario.sh"
    inner_scenario=/out/scenario.sh
fi
if [ "$(basename "$scenario")" = logout-relogin.sh ]; then
    args+=(-e AURORA_RELOGIN_TEST=1)
fi
docker run "${args[@]}" aurora-os-dev bash /src/desktop/dev/session.sh "$inner_scenario" /out
