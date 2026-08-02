#!/bin/bash
# Publish Aurora's packages as a signed apt repository (served by GitHub Pages).
# Usage: tools/publish-apt.sh DEBS_DIR REPO_DIR      (make repo)
#
# Keeps only the newest version of each package, writes Packages, Release,
# InRelease and Release.gpg for suite "trixie", component "main", and signs
# them with the Aurora archive key. The private key lives outside the
# repository, in $AURORA_ARCHIVE_GNUPGHOME (default ~/.config/aurora-os/archive-gnupg);
# its public half is config/keys/aurora-archive-keyring.gpg, installed in the image.
set -euo pipefail
debs=${1:?debs dir}
repo=${2:?repo dir}
suite=trixie
export GNUPGHOME=${AURORA_ARCHIVE_GNUPGHOME:-$HOME/.config/aurora-os/archive-gnupg}
key="Aurora OS Archive"
gpg --list-secret-keys "$key" >/dev/null 2>&1 || {
    echo "publish-apt: signing key '$key' not found in $GNUPGHOME" >&2; exit 1; }

mkdir -p "$repo/pool/main" "$repo/dists/$suite/main/binary-amd64"
for deb in "$debs"/aurora-*_all.deb; do
    name=$(dpkg-deb -f "$deb" Package)
    rm -f "$repo/pool/main/${name}"_*.deb
    cp "$deb" "$repo/pool/main/"
done

cd "$repo"
apt-ftparchive packages pool/main > "dists/$suite/main/binary-amd64/Packages"
gzip -kf9 "dists/$suite/main/binary-amd64/Packages"
apt-ftparchive \
    -o APT::FTPArchive::Release::Origin="Aurora OS" \
    -o APT::FTPArchive::Release::Label="Aurora OS" \
    -o APT::FTPArchive::Release::Suite="$suite" \
    -o APT::FTPArchive::Release::Codename="$suite" \
    -o APT::FTPArchive::Release::Architectures="amd64 all" \
    -o APT::FTPArchive::Release::Components="main" \
    -o APT::FTPArchive::Release::Description="Aurora OS desktop packages" \
    release "dists/$suite" > "dists/$suite/Release"
rm -f "dists/$suite/InRelease" "dists/$suite/Release.gpg"
gpg --batch --yes --local-user "$key" --clearsign -o "dists/$suite/InRelease" "dists/$suite/Release"
gpg --batch --yes --local-user "$key" -abs -o "dists/$suite/Release.gpg" "dists/$suite/Release"
gpg --export "$key" > aurora-archive-keyring.gpg
echo "published: $(ls pool/main | tr '\n' ' ')"
