#!/bin/sh

set -e

repo_root=$(cd "$(dirname "$0")/../../.." && pwd)
shared_dir="$repo_root/skills/glm/_shared"

zai_client_src="$shared_dir/zai_client.py"
oc_harness_src="$shared_dir/oc_harness.py"

zai_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm"
oc_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm brainstorming-glm doc-generator-glm dev-team-glm"

for skill in $zai_skills; do
    dest="$repo_root/skills/glm/$skill/scripts/zai_client.py"
    mkdir -p "$(dirname "$dest")"
    cp "$zai_client_src" "$dest"
    echo "synced $dest"
done

for skill in $oc_skills; do
    dest="$repo_root/skills/glm/$skill/scripts/oc_harness.py"
    mkdir -p "$(dirname "$dest")"
    cp "$oc_harness_src" "$dest"
    echo "synced $dest"
done
