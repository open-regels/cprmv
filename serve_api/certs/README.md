# Bundled certificates

## `certsign-webca.crt`

The **`certSIGN Web CA`** intermediate certificate that signs the leaf certificate
of `repository.officiele-overheidspublicaties.nl`.

That server omits this intermediate from its TLS handshake (it sends the unrelated
`certSIGN Web CA G2` intermediate instead), so OpenSSL/Python cannot build a valid
chain and certificate verification fails. We bundle it here and load it into the
SSL context used for all upstream fetches in [`../src/serve.py`](../src/serve.py).

See [`../SSL_FIX.md`](../SSL_FIX.md) for the full background.

| Field | Value |
|-------|-------|
| Subject | `C=RO, O=CERTSIGN SA, CN=certSIGN Web CA` |
| Issuer | `C=RO, O=CERTSIGN SA, OU=certSIGN ROOT CA G2` |
| Source | leaf cert AIA: `http://www.certsign.ro/certcrl/certsign-webca.crt` |
| Valid until | 2027-02-06 |
| Format | PEM |

This is a public CA certificate (not a secret). To refresh it, see the
**Maintenance** section of [`../SSL_FIX.md`](../SSL_FIX.md).
