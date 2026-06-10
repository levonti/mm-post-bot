#!/bin/sh
set -eu

head_commit="$(git rev-parse HEAD)"
current_tag="${CI_COMMIT_TAG:-}"
previous_tag=""

for tag in $(git tag --merged HEAD --sort=-v:refname --list 'v*'); do
    if ! printf '%s\n' "$tag" | grep -Eq '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
        continue
    fi

    if [ -n "$current_tag" ] && [ "$tag" = "$current_tag" ]; then
        continue
    fi

    tag_commit="$(git rev-list -n 1 "$tag")"
    if [ "$tag_commit" = "$head_commit" ]; then
        continue
    fi

    previous_tag="$tag"
    break
done

if [ -z "$previous_tag" ]; then
    echo "runtime image publish allowed: no previous semver tag found"
    exit 0
fi

changed_files="$(
    git diff --name-only "$previous_tag" HEAD -- \
        Dockerfile \
        .dockerignore \
        pyproject.toml \
        uv.lock \
        src
)"

if [ -n "$changed_files" ]; then
    echo "runtime image inputs changed since $previous_tag:"
    printf '%s\n' "$changed_files"
    exit 0
fi

echo "runtime image inputs did not change since $previous_tag"
exit 1
