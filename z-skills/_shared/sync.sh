#!/bin/sh

set -e

script_dir=$(cd "$(dirname "$0")" && pwd)
dest_root="${1:-$(dirname "$script_dir")}"

zai_client_src="$script_dir/zai_client.py"
zai_skills="z-systematic-debugging z-writing-plans z-requirements-code-audit"

for skill in $zai_skills; do
    dest="$dest_root/$skill/scripts/zai_client.py"
    mkdir -p "$(dirname "$dest")"
    cp "$zai_client_src" "$dest"
    echo "synced $dest"
done

handoff_src="$script_dir/handoff.py"
handoff_skills="z-brainstorming z-dev-team z-doc-generator z-git-diff-summary z-idea-to-spec z-requirements-code-audit z-systematic-debugging z-writing-plans"

for skill in $handoff_skills; do
    dest="$dest_root/$skill/scripts/handoff.py"
    mkdir -p "$(dirname "$dest")"
    cp "$handoff_src" "$dest"
    echo "synced $dest"
done

flash_src="$script_dir/flash_pin.py"
flash_skills="z-dev-team z-systematic-debugging z-writing-plans z-requirements-code-audit"

for skill in $flash_skills; do
    dest="$dest_root/$skill/scripts/flash_pin.py"
    mkdir -p "$(dirname "$dest")"
    cp "$flash_src" "$dest"
    echo "synced $dest"
done

decide_src="$script_dir/decide.py"
decide_skills="z-brainstorming z-writing-plans z-dev-team z-requirements-code-audit z-systematic-debugging z-doc-generator z-git-diff-summary"

for skill in $decide_skills; do
    dest="$dest_root/$skill/scripts/decide.py"
    mkdir -p "$(dirname "$dest")"
    cp "$decide_src" "$dest"
    echo "synced $dest"
done
