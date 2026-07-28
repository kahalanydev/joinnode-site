#!/usr/bin/env bash
# Attaches the live domains to the Coolify app and redeploys so Traefik picks up
# the new router labels and requests certificates. Run only once DNS for
# www.joinnode.ai resolves to the Coolify host, otherwise ACME validation fails
# and burns Let's Encrypt failure-rate budget.
set -u

TOK='33|qxGEe5xLrXK43aV1u2WrY4yiJObk3SpZQmPvcWlX'
HOST='root@178.156.245.71'
APP='xxn3hkg79vaodlgrys6uydcc'
DOMAINS='https://www.joinnode.ai,https://joinnode.ai,https://joinnode.kaymen.dev'

api() { ssh -o StrictHostKeyChecking=no "$HOST" "curl -s $*"; }

api "-X PATCH http://localhost:8000/api/v1/applications/$APP \
  -H 'Authorization: Bearer $TOK' -H 'Accept: application/json' \
  -H 'Content-Type: application/json' -d '{\"domains\":\"$DOMAINS\"}'" >/dev/null

DEP=$(api "-X POST 'http://localhost:8000/api/v1/deploy?uuid=$APP' \
  -H 'Authorization: Bearer $TOK' -H 'Accept: application/json'" \
  | python -c "import sys,json;print(json.load(sys.stdin)['deployments'][0]['deployment_uuid'])" 2>/dev/null)

for _ in $(seq 1 30); do
  st=$(api "http://localhost:8000/api/v1/deployments/$DEP \
    -H 'Authorization: Bearer $TOK' -H 'Accept: application/json'" \
    | python -c "import sys,json;print(json.load(sys.stdin).get('status','?'))" 2>/dev/null)
  case "$st" in finished) break;; failed|error) echo "CUTOVER: deploy $st"; exit 1;; esac
  sleep 10
done

# Traefik requests the certificate on first request for the host.
for _ in $(seq 1 20); do
  code=$(curl -sS -o /dev/null -m 20 -w '%{http_code}' https://www.joinnode.ai/ 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then
    apex=$(curl -sS -o /dev/null -m 20 -w '%{http_code}' https://joinnode.ai/ 2>/dev/null || echo 000)
    echo "CUTOVER COMPLETE - https://www.joinnode.ai returns 200 with a valid certificate (apex: $apex)"
    exit 0
  fi
  sleep 15
done
echo "CUTOVER: domains attached and deployed, but HTTPS not yet answering - needs a look"
exit 1
