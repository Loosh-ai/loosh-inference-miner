# Automated Firewall Management for Miners

This guide describes how to automatically restrict network access to your
miner so that only active Loosh validators can reach it.  The approach uses
the miner-facing Challenge API endpoint `GET /validators/active-hotkeys`,
which returns each active validator's hotkey, status **and IP address**.

> **Prerequisites**
>
> - `ENABLE_VALIDATOR_WHITELIST=true` (default)
> - `CHALLENGE_API_URL` set to the Challenge API base URL
> - Miner hotkey registered on the subnet (used for sr25519 authentication)
> - `curl`, `jq`, and root/sudo access on the miner host

---

## How It Works

1. The miner's built-in `ValidatorWhitelist` already polls
   `GET /validators/active-hotkeys` every 5 minutes using sr25519 hotkey
   signature authentication.
2. An **external cron job** (or systemd timer) calls the same endpoint to
   obtain the current set of validator IPs.
3. The script replaces the miner-port firewall rules with `ACCEPT` entries
   for exactly those IPs, dropping everything else.

This provides **network-level** protection that blocks malicious traffic
before it reaches the application, complementing the application-level
rate limiting and whitelist already built into the miner.

---

## Response Format

```json
[
  {
    "hotkey_ss58": "5F3sa2TJAWMqDhXG6jhV4N8ko9gKph2TGpR67TgeSmcdQk38",
    "status": "active",
    "ip": "203.0.113.42"
  }
]
```

The `ip` field contains the validator's resolved endpoint IP (IPv4 or
IPv6), parsed from the metagraph.  It may be `null` for validators whose
endpoint cannot be resolved — the script below skips those entries.

---

## Signing the Request

The endpoint requires sr25519 hotkey signature authentication.  The
signing scheme uses three headers:

| Header        | Value                                              |
|---------------|----------------------------------------------------|
| `X-Hotkey`    | Miner SS58 address                                 |
| `X-Nonce`     | Unix timestamp in milliseconds                     |
| `X-Signature` | Hex-encoded sr25519 signature of `{nonce}:{hotkey}` |

The helper scripts below use a small Python one-liner (leveraging the
`substrateinterface` library already installed in the miner environment)
to produce the signature.

---

## UFW Script

```bash
#!/usr/bin/env bash
# refresh-validator-firewall-ufw.sh
#
# Dynamically update UFW rules so only active validator IPs can reach
# the miner port.
#
# Usage:
#   CHALLENGE_API_URL=https://challenge.loosh.ai \
#   MINER_SS58=5F3sa... \
#   MINER_SEED=0x... \
#   MINER_PORT=8000 \
#   ./refresh-validator-firewall-ufw.sh
#
# Schedule via cron:
#   */5 * * * * /opt/miner/refresh-validator-firewall-ufw.sh >> /var/log/firewall-refresh.log 2>&1

set -euo pipefail

CHALLENGE_API="${CHALLENGE_API_URL:?CHALLENGE_API_URL is required}"
MINER_SS58="${MINER_SS58:?MINER_SS58 is required}"
MINER_SEED="${MINER_SEED:?MINER_SEED is required}"
MINER_PORT="${MINER_PORT:-8000}"

# --- Generate auth headers ---
read -r NONCE SIG <<< "$(python3 -c "
import time, binascii
from substrateinterface import Keypair
kp = Keypair.create_from_seed('${MINER_SEED}')
nonce = str(int(time.time() * 1000))
msg = f'{nonce}:${MINER_SS58}'
sig = binascii.hexlify(kp.sign(msg)).decode()
print(nonce, sig)
")"

# --- Fetch active validator IPs ---
RESPONSE=$(curl -sS --max-time 15 \
    -H "X-Hotkey: ${MINER_SS58}" \
    -H "X-Nonce: ${NONCE}" \
    -H "X-Signature: ${SIG}" \
    "${CHALLENGE_API}/validators/active-hotkeys")

VALIDATOR_IPS=$(echo "${RESPONSE}" | jq -r '.[].ip // empty' | sort -u)

if [ -z "${VALIDATOR_IPS}" ]; then
    echo "$(date): WARNING — no validator IPs returned, keeping existing rules"
    exit 0
fi

# --- Rebuild rules ---
# Delete existing rules for the miner port (both allow and deny)
while sudo ufw status numbered | grep -q "${MINER_PORT}/tcp"; do
    RULE_NUM=$(sudo ufw status numbered | grep "${MINER_PORT}/tcp" | head -1 | sed 's/\[//;s/\].*//' | tr -d ' ')
    yes | sudo ufw delete "${RULE_NUM}" > /dev/null 2>&1
done

# Allow each validator IP
COUNT=0
for ip in ${VALIDATOR_IPS}; do
    sudo ufw allow from "${ip}" to any port "${MINER_PORT}" proto tcp > /dev/null 2>&1
    COUNT=$((COUNT + 1))
done

# Deny all other traffic to the miner port
sudo ufw deny "${MINER_PORT}/tcp" > /dev/null 2>&1

echo "$(date): Firewall updated — ${COUNT} validator IPs allowed on port ${MINER_PORT}"
```

---

## iptables Script

For operators who prefer raw iptables (or don't have UFW):

```bash
#!/usr/bin/env bash
# refresh-validator-firewall-iptables.sh
#
# Uses a dedicated chain LOOSH_VALIDATORS to manage rules atomically.

set -euo pipefail

CHALLENGE_API="${CHALLENGE_API_URL:?CHALLENGE_API_URL is required}"
MINER_SS58="${MINER_SS58:?MINER_SS58 is required}"
MINER_SEED="${MINER_SEED:?MINER_SEED is required}"
MINER_PORT="${MINER_PORT:-8000}"
CHAIN_NAME="LOOSH_VALIDATORS"

read -r NONCE SIG <<< "$(python3 -c "
import time, binascii
from substrateinterface import Keypair
kp = Keypair.create_from_seed('${MINER_SEED}')
nonce = str(int(time.time() * 1000))
msg = f'{nonce}:${MINER_SS58}'
sig = binascii.hexlify(kp.sign(msg)).decode()
print(nonce, sig)
")"

RESPONSE=$(curl -sS --max-time 15 \
    -H "X-Hotkey: ${MINER_SS58}" \
    -H "X-Nonce: ${NONCE}" \
    -H "X-Signature: ${SIG}" \
    "${CHALLENGE_API}/validators/active-hotkeys")

VALIDATOR_IPS=$(echo "${RESPONSE}" | jq -r '.[].ip // empty' | sort -u)

if [ -z "${VALIDATOR_IPS}" ]; then
    echo "$(date): WARNING — no validator IPs returned, keeping existing rules"
    exit 0
fi

# Create or flush the chain
sudo iptables -N "${CHAIN_NAME}" 2>/dev/null || sudo iptables -F "${CHAIN_NAME}"

# Accept from each validator IP
COUNT=0
for ip in ${VALIDATOR_IPS}; do
    sudo iptables -A "${CHAIN_NAME}" -s "${ip}" -j ACCEPT
    COUNT=$((COUNT + 1))
done

# Drop everything else in this chain
sudo iptables -A "${CHAIN_NAME}" -j DROP

# Wire the chain into INPUT for the miner port (idempotent)
if ! sudo iptables -C INPUT -p tcp --dport "${MINER_PORT}" -j "${CHAIN_NAME}" 2>/dev/null; then
    sudo iptables -I INPUT -p tcp --dport "${MINER_PORT}" -j "${CHAIN_NAME}"
fi

echo "$(date): iptables updated — ${COUNT} validator IPs allowed on port ${MINER_PORT}"
```

---

## nftables Script

For modern Linux distributions using nftables:

```bash
#!/usr/bin/env bash
# refresh-validator-firewall-nft.sh
#
# Uses an nftables set for atomic swap of allowed IPs.

set -euo pipefail

CHALLENGE_API="${CHALLENGE_API_URL:?CHALLENGE_API_URL is required}"
MINER_SS58="${MINER_SS58:?MINER_SS58 is required}"
MINER_SEED="${MINER_SEED:?MINER_SEED is required}"
MINER_PORT="${MINER_PORT:-8000}"

read -r NONCE SIG <<< "$(python3 -c "
import time, binascii
from substrateinterface import Keypair
kp = Keypair.create_from_seed('${MINER_SEED}')
nonce = str(int(time.time() * 1000))
msg = f'{nonce}:${MINER_SS58}'
sig = binascii.hexlify(kp.sign(msg)).decode()
print(nonce, sig)
")"

RESPONSE=$(curl -sS --max-time 15 \
    -H "X-Hotkey: ${MINER_SS58}" \
    -H "X-Nonce: ${NONCE}" \
    -H "X-Signature: ${SIG}" \
    "${CHALLENGE_API}/validators/active-hotkeys")

VALIDATOR_IPS=$(echo "${RESPONSE}" | jq -r '.[].ip // empty' | sort -u)

if [ -z "${VALIDATOR_IPS}" ]; then
    echo "$(date): WARNING — no validator IPs returned, keeping existing rules"
    exit 0
fi

# Build the nftables set elements
ELEMENTS=""
for ip in ${VALIDATOR_IPS}; do
    ELEMENTS="${ELEMENTS}${ip}, "
done
ELEMENTS="${ELEMENTS%, }"

# Apply atomically
sudo nft -f - <<NFT_EOF
table inet loosh_miner {
    set validator_ips {
        type ipv4_addr
        flags interval
        elements = { ${ELEMENTS} }
    }

    chain miner_input {
        type filter hook input priority filter; policy accept;
        tcp dport ${MINER_PORT} ip saddr @validator_ips accept
        tcp dport ${MINER_PORT} drop
    }
}
NFT_EOF

COUNT=$(echo "${VALIDATOR_IPS}" | wc -w)
echo "$(date): nftables updated — ${COUNT} validator IPs allowed on port ${MINER_PORT}"
```

---

## systemd Timer (Alternative to Cron)

For a more robust scheduling mechanism:

```ini
# /etc/systemd/system/loosh-firewall-refresh.service
[Unit]
Description=Refresh Loosh miner firewall rules
After=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/opt/miner/.env
ExecStart=/opt/miner/refresh-validator-firewall-ufw.sh
StandardOutput=journal
StandardError=journal
```

```ini
# /etc/systemd/system/loosh-firewall-refresh.timer
[Unit]
Description=Refresh Loosh miner firewall every 5 minutes

[Timer]
OnBootSec=30s
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now loosh-firewall-refresh.timer
```

---

## Docker Environments

When the miner runs inside Docker, firewall rules must be applied on the
**host**, not inside the container.  Docker's port mapping (`-p 8000:8000`)
bypasses the INPUT chain and routes through the DOCKER chain.

### Option A — Docker with iptables (DOCKER-USER chain)

Docker provides the `DOCKER-USER` chain for user-defined rules that are
evaluated before Docker's own forwarding rules:

```bash
# In the iptables script, replace the chain wiring with:
CHAIN_NAME="LOOSH_VALIDATORS"

# ... (same IP-fetching logic as above) ...

sudo iptables -N "${CHAIN_NAME}" 2>/dev/null || sudo iptables -F "${CHAIN_NAME}"

for ip in ${VALIDATOR_IPS}; do
    sudo iptables -A "${CHAIN_NAME}" -s "${ip}" -j RETURN
done
sudo iptables -A "${CHAIN_NAME}" -j DROP

if ! sudo iptables -C DOCKER-USER -p tcp --dport "${MINER_PORT}" -j "${CHAIN_NAME}" 2>/dev/null; then
    sudo iptables -I DOCKER-USER -p tcp --dport "${MINER_PORT}" -j "${CHAIN_NAME}"
fi
```

### Option B — Host networking

If using `--network host`, the standard INPUT chain scripts above work
without modification.

---

## Verifying the Setup

After the script runs, verify the rules:

```bash
# UFW
sudo ufw status verbose | grep 8000

# iptables
sudo iptables -L LOOSH_VALIDATORS -n -v

# nftables
sudo nft list set inet loosh_miner validator_ips
```

Test that a blocked IP is rejected:

```bash
# From a non-validator IP
curl -v --connect-timeout 5 http://<MINER_IP>:8000/availability
# Expected: connection refused or timeout
```

---

## Security Considerations

- **Never expose the miner seed** in plaintext files.  Use a secrets
  manager, environment file with restricted permissions (`chmod 600`), or
  a hardware security module.
- The firewall scripts use a **fail-safe** approach: if the Challenge API
  returns zero IPs (network error, outage), existing rules are preserved
  rather than flushing all access.
- Validator IPs change infrequently but they **do** change.  A 5-minute
  refresh interval matches the miner's internal whitelist refresh cycle.
- These scripts complement the miner's application-level protections
  (hotkey whitelist, rate limiting, signature verification).  Use both
  layers for defence in depth.
- The `ip` field in the API response is derived from the validator's
  on-chain `resolved_endpoint`.  This is the same information publicly
  available on the Bittensor metagraph.
