#!/bin/sh

set -e

script_dir=$(cd "$(dirname "$0")" && pwd)
dest_root="${1:-$(dirname "$script_dir")}"

zai_client_src="$script_dir/zai_client.py"
zai_skills="glm-systematic-debugging glm-writing-plans glm-requirements-code-audit"

for skill in $zai_skills; do
    dest="$dest_root/$skill/scripts/zai_client.py"
    mkdir -p "$(dirname "$dest")"
    cp "$zai_client_src" "$dest"
    echo "synced $dest"
done
