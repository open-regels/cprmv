# TLS / certificate fix for `repository.officiele-overheidspublicaties.nl`

## Symptom

Every CPRMV rule lookup that needs to fetch a source publication (any `BWBR…` /
`CVDR…` identifier) returned an error payload instead of data:

```json
{"error": "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1010)>"}
```

Note that the API still answered with **HTTP 200** — the failure was wrapped into
the response body, so clients could easily mistake it for a valid result.

## Root cause

The upstream repository `repository.officiele-overheidspublicaties.nl` serves an
**incomplete / incorrect TLS certificate chain**. The chain it presents during the
handshake is:

| # | Subject | Issued by |
|---|---------|-----------|
| 0 (leaf) | `repository.officiele-overheidspublicaties.nl` | **`certSIGN Web CA`** |
| 1 | `certSIGN Web CA **G2**` | `certSIGN ROOT CA G2` |
| 2 | `certSIGN ROOT CA G2` | (self-signed root) |

The leaf certificate is signed by **`certSIGN Web CA`**, but the intermediate the
server actually sends is **`certSIGN Web CA G2`** — a *different* CA. The
intermediate that genuinely signed the leaf is **missing** from the handshake.

As a result, no OpenSSL-based client (Python's `urllib`, `requests`, `curl`, …)
can build a path from the leaf to a trusted root, and verification fails with
`unable to get local issuer certificate`.

### Why it "works in a browser"

Browsers implement **AIA fetching**: they read the *Authority Information Access*
extension of the leaf certificate and download the missing issuing certificate on
the fly. The leaf here advertises:

```
Authority Information Access:
    CA Issuers - URI:http://www.certsign.ro/certcrl/certsign-webca.crt
```

Python/OpenSSL do **not** do AIA fetching, so they fail where the browser silently
succeeds. This is the entire "works in the browser, fails in Python" gap — it is a
misconfiguration on the government server, not a bug in this code or in the client
machine.

## The fix

We cannot change the upstream server, so we supply the missing intermediate
ourselves. The correct, *secure* fix keeps certificate verification fully enabled
and simply adds the one certificate the server should have sent.

1. The missing intermediate is vendored at
   [`certs/certsign-webca.crt`](certs/certsign-webca.crt) (downloaded from the
   leaf's AIA URL above — see [`certs/README.md`](certs/README.md) for provenance).
2. [`src/serve.py`](src/serve.py) builds a single module-level `ssl.SSLContext`
   that loads the system trust store **plus** this bundled intermediate, and
   passes it to every outbound `urlopen(...)` call:

   ```python
   _BUNDLED_INTERMEDIATE = Path(__file__).resolve().parent.parent / "certs" / "certsign-webca.crt"

   def _build_ssl_context() -> ssl.SSLContext:
       ctx = ssl.create_default_context()
       if _BUNDLED_INTERMEDIATE.is_file():
           ctx.load_verify_locations(cafile=str(_BUNDLED_INTERMEDIATE))
       return ctx

   SSL_CONTEXT = _build_ssl_context()
   # ... urlopen(req, context=SSL_CONTEXT)
   ```

This single mechanism is **OS-independent** and covers both run modes:

- **Local / non-Docker** (Windows, macOS, Linux): the cert is loaded from the repo
  at runtime — no system-level certificate installation needed.
- **Docker**: the [`Dockerfile`](Dockerfile) copies `certs/` into the image
  (`COPY certs/ ./certs/`) so the same code path finds it.

### Why not the alternatives

- **Disabling verification** (`ssl._create_unverified_context()` / `verify=False`)
  would also "work", but it turns off authentication for *all* upstreams and is a
  security regression. Rejected.
- **Installing into the OS trust store** (`update-ca-certificates`) only helps on
  Linux/Docker and requires per-OS steps for local runs. The code-level context is
  simpler and portable, so it is the single source of truth.

## Maintenance

The bundled intermediate `certSIGN Web CA` is valid until **2027-02-06**. When
certSIGN rotates it, refresh the bundled copy:

```bash
# Re-fetch the current intermediate advertised by the leaf's AIA extension
host=repository.officiele-overheidspublicaties.nl
curl -s http://www.certsign.ro/certcrl/certsign-webca.crt -o /tmp/webca.crt
openssl x509 -inform DER -in /tmp/webca.crt -out certs/certsign-webca.crt   # normalize to PEM
# Sanity check: subject must match the leaf's issuer
openssl x509 -in certs/certsign-webca.crt -noout -subject -issuer -enddate
```

The proper long-term fix is for the operator of
`repository.officiele-overheidspublicaties.nl` to correct its server
configuration to send the matching `certSIGN Web CA` intermediate. Until then,
this workaround is required.

## How to verify

```bash
# Should fail WITHOUT the bundled cert and succeed WITH it:
python - <<'PY'
import ssl, socket
from pathlib import Path
host = "repository.officiele-overheidspublicaties.nl"
for load in (False, True):
    ctx = ssl.create_default_context()
    if load:
        ctx.load_verify_locations(cafile="certs/certsign-webca.crt")
    try:
        with socket.create_connection((host, 443), timeout=10) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                print("load_bundled =", load, "->", "OK", ss.version())
    except Exception as e:
        print("load_bundled =", load, "->", "FAIL", e)
PY
```

End-to-end, a rule lookup such as

```
GET /rules/BWBR0015703%2C%20Artikel%2020%2C%20lid%201%2C%20onderdeel%20a.?unformat=...&format=cprmv-json
```

now returns a real CPRMV `RuleSet` instead of the `{"error": ...}` payload.
