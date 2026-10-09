#!/usr/bin/env bash
# Run from Linux/WSL with Docker. Only invocation-owned containers/network are removed.
set -euo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$root"
owner="copilot-$(date -u +%Y%m%dT%H%M%S)-$$"
network="flowpilot-$owner"
database="flowpilot-pg-$owner"
validation="flowpilot-tests-$owner"
image="flowpilot-copilot-current-validation"
label="flowpilot.validation.owner"
cleanup() {
  for container in "$validation" "$database"; do
    actual=$(docker inspect --format "{{index .Config.Labels \"$label\"}}" "$container" 2>/dev/null || true)
    if [[ "$actual" == "$owner" ]]; then docker rm -f "$container" >/dev/null; fi
  done
  actual=$(docker network inspect --format "{{index .Labels \"$label\"}}" "$network" 2>/dev/null || true)
  if [[ "$actual" == "$owner" ]]; then docker network rm "$network" >/dev/null; fi
}
trap cleanup EXIT
printf 'Source commit: %s\n' "$(git rev-parse HEAD)"
docker build -f backend/Dockerfile -t "$image" .
docker image inspect --format 'Validated image: {{.Id}}' "$image"
docker network create --label "$label=$owner" "$network" >/dev/null
docker run -d --name "$database" --label "$label=$owner" --network "$network" \
  --network-alias validation-postgres --tmpfs /var/lib/postgresql/data:rw,size=1g \
  -e POSTGRES_USER=fp_validation -e POSTGRES_PASSWORD=isolated-fixture-only \
  -e POSTGRES_DB=fp_validation postgres:16 >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$database" pg_isready -U fp_validation -d fp_validation >/dev/null; then ready=true; break; fi
  sleep 1
done
[[ "$ready" == true ]] || { echo 'Owned PostgreSQL did not become ready' >&2; exit 1; }
docker exec "$database" postgres --version
tests=()
test_files() {
  if command -v rg >/dev/null; then
    rg --files backend/tests -g 'test_copilot_*.py' -g 'test_*_20*.py' \
      -g 'test_base_upstream_language_17r.py' -g 'test_base_runtime_packaging_17s.py'
  else
    find backend/tests -maxdepth 1 -type f \( -name 'test_copilot_*.py' -o -name 'test_*_20*.py' \
      -o -name 'test_base_upstream_language_17r.py' -o -name 'test_base_runtime_packaging_17s.py' \)
  fi
}
while IFS= read -r path; do tests+=("/validation/tests/${path##*/}"); done < <(
  test_files | sort
)
[[ ${#tests[@]} -gt 0 ]]
docker run --rm --name "$validation" --label "$label=$owner" --network "$network" \
  --mount "type=bind,source=$root/backend/tests,target=/validation/tests,readonly" \
  --mount "type=bind,source=$root/backend/migrations,target=/validation/migrations,readonly" \
  --mount "type=bind,source=$root/backend/alembic.ini,target=/validation/alembic.ini,readonly" \
  -e PYTHONPATH=/app:/validation/tests -e DATABASE_URL=sqlite:///:memory: \
  -e AUTO_CREATE_SCHEMA_ON_STARTUP=false -e APP_ENV=test \
  -e FLOWPILOT_TEST_POSTGRES_URL=postgresql+psycopg2://fp_validation:isolated-fixture-only@validation-postgres/fp_validation \
  "$image" sh -c 'python --version; node --version; python -m pytest -q -p no:cacheprovider "$@"' sh "${tests[@]}"
schemas=$(docker exec "$database" psql -U fp_validation -d fp_validation -At \
  -c "SELECT count(*) FROM information_schema.schemata WHERE schema_name LIKE 'fp_test_%'")
printf 'Remaining temporary schemas: %s\n' "$schemas"
[[ "$schemas" == 0 ]]
printf 'Packaged Copilot regression passed; invocation-owned runtime cleanup follows.\n'
