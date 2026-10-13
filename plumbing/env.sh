#!/usr/bin/env bash
# Shared environment for the plumbing scripts (source me).
#
#   . plumbing/env.sh
#
# Sets REPO_ROOT / PLUMBING_DIR, GCP_ROOT (the bucket root, unless already
# exported) and GCP_PREFIX (this repo's prefix under it), plus gcs_cp / gcs_cat
# / gcs_ls / gcs_rsync wrappers. Prefers `gcloud storage` (Google's recommended
# CLI) and falls back to `gsutil`.

PLUMBING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$PLUMBING_DIR/.." && pwd)"
export PLUMBING_DIR REPO_ROOT

# This repo's prefix lives at the BUCKET ROOT, not under the parent project's
# prefix: gs://akbar-december-2024-backup/arabmaqamrock/. Kept in its own
# variable (GCP_ROOT) on purpose, so the parent's GCP_BACKUP_BASE — which is a
# *project prefix* (.../OSTRIS_Arabic_Suno_Finetuning), not a bucket root —
# never silently relocates this one. Override GCP_ROOT for a different bucket.
: "${GCP_ROOT:=gs://akbar-december-2024-backup}"
export GCP_ROOT
export GCP_PREFIX="${GCP_ROOT%/}/arabmaqamrock"

if command -v gcloud >/dev/null 2>&1; then
  gcs_cp()    { gcloud storage cp "$@"; }
  gcs_cat()   { gcloud storage cat "$@"; }
  gcs_ls()    { gcloud storage ls "$@"; }
  gcs_rsync() { gcloud storage rsync "$@"; }
  export GCS_CLI=gcloud
elif command -v gsutil >/dev/null 2>&1; then
  gcs_cp()    { gsutil cp "$@"; }
  gcs_cat()   { gsutil cat "$@"; }
  gcs_ls()    { gsutil ls "$@"; }
  gcs_rsync() { gsutil -m rsync "$@"; }
  export GCS_CLI=gsutil
else
  echo "plumbing/env.sh: need 'gcloud' or 'gsutil' on PATH" >&2
  export GCS_CLI=
fi
