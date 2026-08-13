#!/bin/sh
set -eu

example=${MOLDGUARD_ENV_EXAMPLE:-.env.competition.example}
target=${MOLDGUARD_ENV_FILE:-.env.competition}

if [ ! -f "$example" ]; then
    echo "Environment example not found: ${example}" >&2
    exit 2
fi
if [ -e "$target" ]; then
    echo "Refusing to overwrite existing environment file: ${target}" >&2
    exit 2
fi
if ! command -v openssl >/dev/null 2>&1; then
    echo "openssl is required to generate deployment secrets." >&2
    exit 2
fi

django_secret=$(openssl rand -hex 48)
database_password=$(openssl rand -hex 32)
root_password=$(openssl rand -hex 32)
temporary=$(mktemp "${target}.tmp.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM
umask 077

sed \
    -e "s|replace-with-a-long-random-secret|${django_secret}|g" \
    -e "s|replace-with-a-long-random-password|${database_password}|g" \
    -e "s|replace-with-a-different-long-random-password|${root_password}|g" \
    "$example" > "$temporary"

if grep -q 'replace-with-' "$temporary"; then
    echo "Environment generation left unresolved placeholders." >&2
    exit 1
fi

chmod 600 "$temporary"
mv "$temporary" "$target"
trap - EXIT HUP INT TERM
echo "Created ${target} with mode 600. Secret values were not printed."
