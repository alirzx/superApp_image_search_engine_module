#!/bin/sh
# Install OS packages using signed Debian Bookworm repositories and fast failover.
# Called only at Docker build time, so a persistent server environment is not altered.
set -eu

if [ "$#" -eq 0 ]; then
  echo "Usage: install-debian-packages.sh <package> ..." >&2
  exit 2
fi

primary_debian="${APT_PRIMARY_DEBIAN_URL:-https://mirror.metanet.ch/debian}"
primary_security="${APT_PRIMARY_SECURITY_URL:-https://mirror.metanet.ch/debian-security}"
fallback_debian="${APT_FALLBACK_DEBIAN_URL:-https://mirrors.huaweicloud.com/repository/debian}"
fallback_security="${APT_FALLBACK_SECURITY_URL:-https://mirrors.huaweicloud.com/repository/debian-security}"

for url in "$primary_debian" "$primary_security" "$fallback_debian" "$fallback_security"; do
  case "$url" in
    https://*) ;;
    *) echo "APT mirrors must be HTTPS URLs" >&2; exit 2 ;;
  esac
done

sources=/etc/apt/sources.list.d/debian.sources
if [ ! -f /usr/share/keyrings/debian-archive-keyring.gpg ]; then
  echo "Missing Debian archive keyring; refusing unverified APT repositories" >&2
  exit 1
fi

write_sources() {
  # Replace, rather than append to, the image's stock Debian sources.
  # The original http://deb.debian.org entries must not be contacted.
  rm -f /etc/apt/sources.list
  cat > "$sources" <<EOF
Types: deb
URIs: $1
Suites: bookworm bookworm-updates
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: $2
Suites: bookworm-security
Components: main
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
}

attempt() {
  label="$1"
  main_mirror="$2"
  security_mirror="$3"
  shift 3
  echo "Trying signed Debian Bookworm APT mirror: $label"
  write_sources "$main_mirror" "$security_mirror"
  # Do not let apt-get update succeed with incomplete/stale package indexes.
  rm -rf /var/lib/apt/lists/*
  mkdir -p /var/lib/apt/lists/partial
  if ! apt-get -o APT::Update::Error-Mode=any \
      -o Acquire::Retries=1 -o Acquire::http::Timeout=20 \
      -o Acquire::https::Timeout=20 update; then
    echo "APT index refresh failed for $label" >&2
    return 1
  fi
  if ! DEBIAN_FRONTEND=noninteractive apt-get -y \
      -o Acquire::Retries=1 -o Acquire::http::Timeout=20 \
      -o Acquire::https::Timeout=20 install --no-install-recommends "$@"; then
    echo "APT package installation failed for $label" >&2
    return 1
  fi
  return 0
}

if attempt primary "$primary_debian" "$primary_security" "$@"; then
  echo "APT primary mirror succeeded"
elif attempt fallback "$fallback_debian" "$fallback_security" "$@"; then
  echo "APT fallback mirror succeeded"
else
  echo "Both Debian APT mirrors failed: inspect server egress, TLS and DNS." >&2
  exit 1
fi

rm -rf /var/lib/apt/lists/*
