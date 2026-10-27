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

handoff_src="$script_dir/handoff.py"
handoff_skills="glm-brainstorming glm-dev-team glm-doc-generator glm-git-diff-summary glm-idea-to-spec glm-requirements-code-audit glm-systematic-debugging glm-writing-plans"

for skill in $handoff_skills; do
    dest="$dest_root/$skill/scripts/handoff.py"
    mkdir -p "$(dirname "$dest")"
    cp "$handoff_src" "$dest"
    echo "synced $dest"
done
