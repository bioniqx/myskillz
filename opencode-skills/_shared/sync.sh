#!/bin/sh

set -e

script_dir=$(cd "$(dirname "$0")" && pwd)
dest_root="${1:-$(dirname "$script_dir")}"

oc_harness_src="$script_dir/oc_harness.py"

oc_skills="oc-brainstorming oc-dev-team oc-doc-generator oc-requirements-code-audit oc-systematic-debugging oc-writing-plans"

for skill in $oc_skills; do
    dest="$dest_root/$skill/scripts/oc_harness.py"
    mkdir -p "$(dirname "$dest")"
    cp "$oc_harness_src" "$dest"
    echo "synced $dest"
done
