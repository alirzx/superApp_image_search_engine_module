#!/usr/bin/env sh
set -eu
mkdir -p .data .models/siglip2
printf 'Created .data and .models/siglip2 as uid=%s gid=%s\n' "$(id -u)" "$(id -g)"
printf 'Ensure RUN_UID=%s and RUN_GID=%s in .env\n' "$(id -u)" "$(id -g)"
