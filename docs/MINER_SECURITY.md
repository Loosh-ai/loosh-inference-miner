# Miner Security & DDoS Mitigation

Because miner IPs and ports are registered on the Bittensor metagraph, they
are publicly discoverable by anyone who can query the chain.  This document
describes the layered defences built into the miner software and recommends
additional infrastructure-level protections that operators should deploy.

---

## Built-in Application-Level Protections

### 1. Validator Signature Verification

Every Fiber key-exchange request carries an `sr25519` signature produced by
the validator's hotkey.  The miner reconstructs the signed message
(`{timestamp}.{nonce}.{validator_hotkey_ss58}`) and verifies it against the
claimed SS58 address **before** performing the expensive RSA decryption step.
Requests with invalid or missing signatures are rejected immediately.

### 2. Validator Hotkey Whitelist

When `ENABLE_VALIDATOR_WHITELIST=true` (the default), the miner maintains a
set of known validator hotkeys sourced from:

1. **The Bittensor metagraph** — nodes with `validator_permit=True` on the
   configured subnet.  Refreshed every 5 minutes.
2. **The Challenge API** (optional) — if `CHALLENGE_API_URL` is set, the
   miner polls `GET /validators/active-hotkeys` for an authoritative list
   of active validators, also refreshed every 5 minutes.  The miner
   authenticates to this endpoint using **sr25519 hotkey signatures**
   (same scheme as validators: `X-Hotkey`, `X-Nonce`, `X-Signature`
   headers).  The Challenge API verifies the signature and checks that
   the calling hotkey is registered on the subnet.

Requests from hotkeys **not** in the whitelist are rejected with `403
Forbidden` before any crypto work or inference is performed.

During the bootstrap period (before the first metagraph sync completes) the
whitelist is empty and all hotkeys are temporarily allowed.

| Environment variable      | Default | Description                                    |
|---------------------------|---------|------------------------------------------------|
| `ENABLE_VALIDATOR_WHITELIST` | `true`  | Enable/disable the whitelist gate              |
| `CHALLENGE_API_URL`       | *(none)* | Challenge API base URL (e.g. `https://challenge.loosh.ai`) |
| `CHALLENGE_API_KEY`       | *(none)* | **Deprecated** — kept for backward compat with older Challenge API deployments. The miner now authenticates with its sr25519 hotkey. |

### 3. IP-Aware Rate Limiting

A middleware layer enforces per-source-IP and per-claimed-hotkey request
limits using fixed-window counters (60-second window).  IPs that match a
known active validator (sourced from the Challenge API's
`/validators/active-hotkeys` endpoint) receive **relaxed** limits, while
all unknown IPs are subject to **strict** thresholds.

**Known (validator) IPs:**

| Endpoint               | Per-IP limit | Per-hotkey limit |
|------------------------|-------------|-----------------|
| `GET /availability`    | 20/min       | 60/min          |
| `GET /fiber/public-key`| 20/min       | —               |
| `POST /fiber/key-exchange` | 30/min   | 60/min          |
| `POST /fiber/challenge`| 120/min      | 60/min          |
| `POST /inference`      | 60/min       | 60/min          |
| Other paths            | 60/min       | 60/min          |

**Unknown IPs:**

| Endpoint               | Per-IP limit | Per-hotkey limit |
|------------------------|-------------|-----------------|
| `GET /availability`    | 6/min        | 60/min          |
| `GET /fiber/public-key`| 6/min        | —               |
| `POST /fiber/key-exchange` | 10/min   | 60/min          |
| `POST /fiber/challenge`| 30/min       | 60/min          |
| `POST /inference`      | 15/min       | 60/min          |
| Other paths            | 15/min       | 60/min          |

Requests exceeding the limit receive `429 Too Many Requests` with a
`Retry-After` header.

The validator IP set is populated automatically from the Challenge API
poll and requires no additional configuration beyond the standard
`CHALLENGE_API_URL` setting.

### 4. Uvicorn Connection Limits

The uvicorn server is configured with:

| Flag                     | Default | Description                                     |
|--------------------------|---------|-------------------------------------------------|
| `--timeout-keep-alive`   | `5`     | Closes idle keepalive connections after 5 s      |
| `--limit-concurrency`    | `50`    | Maximum simultaneous connections                 |
| `--limit-max-requests`   | `10000` | Worker restarts after N requests (memory safety) |

Override via environment variables `UVICORN_KEEP_ALIVE`,
`UVICORN_LIMIT_CONCURRENCY`, `UVICORN_LIMIT_MAX_REQUESTS` in Docker.

### 5. Concurrency Semaphore

The existing `max_concurrent_requests` (default 10) limits how many
inference requests are processed simultaneously.  Excess requests are
queued FIFO and processed as capacity becomes available.

---

## Recommended Infrastructure Protections

The application-level defences above mitigate abuse at the request level,
but they cannot prevent TCP-level attacks (SYN floods, connection
exhaustion) from reaching the process.  For full protection, deploy one or
more of the following.

### Reverse Proxy (nginx)

Running nginx in front of the miner application provides connection-level
rate limiting and slow-client protection.  Example configuration:

```nginx
# /etc/nginx/conf.d/miner.conf

limit_req_zone  $binary_remote_addr  zone=miner_ip:10m  rate=30r/m;
limit_conn_zone $binary_remote_addr  zone=miner_conn:10m;

upstream miner_backend {
    server 127.0.0.1:8000;
}

server {
    listen 8080;

    # Connection limits
    limit_conn miner_conn 10;

    # Request rate limit (burst allows short validator challenge bursts)
    limit_req zone=miner_ip burst=20 nodelay;

    # Slow-client protection
    client_body_timeout   10s;
    client_header_timeout 5s;
    send_timeout          30s;

    # Request body size limit (challenges are small)
    client_max_body_size 1m;

    location / {
        proxy_pass http://miner_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

With this setup, register the **nginx** port (8080) with `fiber-post-ip`
instead of the application port (8000), and bind the application to
`127.0.0.1:8000` so it is not directly reachable from the internet.

### Firewall Rules (UFW / iptables / nftables)

Restrict port access to known validator IPs only.  The Challenge API's
`GET /validators/active-hotkeys` endpoint now includes each validator's
`ip` field, making automated firewall management straightforward.

See **[docs/AUTOMATED_FIREWALL.md](AUTOMATED_FIREWALL.md)** for complete
scripts covering UFW, iptables, nftables, Docker, and systemd timer
scheduling.

### Cloud Provider DDoS Protection

If running on a cloud provider, enable their native DDoS protection:

- **AWS**: AWS Shield Standard (free) + Security Groups
- **GCP**: Cloud Armor
- **Azure**: Azure DDoS Protection
- **RunPod**: Use the built-in firewall and expose only the miner port

---

## Attack Scenarios and Mitigations

| Attack                         | Vector                            | Mitigation                                    |
|--------------------------------|-----------------------------------|-----------------------------------------------|
| Port/connection exhaustion     | Thousands of TCP connections       | Uvicorn `--limit-concurrency`, reverse proxy   |
| Key-exchange CPU exhaustion    | Repeated POST `/fiber/key-exchange`| Signature verification, whitelist, rate limit  |
| Fake challenge flood           | POST `/fiber/challenge` with junk  | Whitelist + pre-flight key check rejects fast  |
| Availability endpoint flood    | GET `/availability` flood          | Per-IP rate limit (10/min)                     |
| Slow loris                     | Slow HTTP writes holding connections| Uvicorn `--timeout-keep-alive`, nginx timeouts |
| Miner-to-miner attack          | Reading metagraph for victim IPs   | Firewall rules, reverse proxy                  |
