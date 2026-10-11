# Version 1 contracts

FastAPI/Pydantic definitions in `services/ride_service/app.py` are the executable schema. A generated snapshot is checked in as `contracts/openapi.json`. Retrieve `/openapi.json` from a running backend to inspect the generated schema. Command and event wire records declare `schema_version=1`; all episode identities are run-scoped. Domain versions, sequence numbers, retries, freshness and exceptional behavior are specified in `docs/protocol.md`.

Create requires `Idempotency-Key`; identity is scoped to client ID plus endpoint. Expected revision is required for passenger cancellation/readiness and operator pickup changes. Unknown origin/destination and invalid numeric bounds receive 422; conflicts receive 409; unknown rides receive 404. A competing request is rejected explicitly, with no hidden queue.

Application events are trusted synthetic local-agent evidence; no cryptographic attestation or production authentication is claimed. Raw observed edge, lane position, speed and stopped flag accompany progress; backend guards observations as well as lifecycle order.
