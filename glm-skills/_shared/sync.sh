#!/bin/sh

set -e

script_dir=$(cd "$(dirname "$0")" && pwd)
dest_root="${1:-$(dirname "$script_dir")}"

zai_client_src="$script_dir/zai_client.py"
oc_harness_src="$script_dir/oc_harness.py"

zai_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm"
oc_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm brainstorming-glm doc-generator-glm dev-team-glm"

for skill in $zai_skills; do
    dest="$dest_root/$skill/scripts/zai_client.py"
    mkdir -p "$(dirname "$dest")"
    cp "$zai_client_src" "$dest"
    echo "synced $dest"
done

for skill in $oc_skills; do
    dest="$dest_root/$skill/scripts/oc_harness.py"
    mkdir -p "$(dirname "$dest")"
    cp "$oc_harness_src" "$dest"
    echo "synced $dest"
done
