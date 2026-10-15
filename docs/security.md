# Security and safe testing checklist

RescueGrid is an educational prototype. Do not connect it to live traffic signals or deploy it on a public or untrusted network.

## Known limitations

- Central-server and junction endpoints do not yet enforce a complete authentication and authorization policy. CORS is not authentication and does not stop non-browser clients.
- Sample junction commands use plain HTTP and need TLS or a protected network tunnel for controlled trials.
- The dashboard WebSocket URL is configured in `dashboard/app.js`; use WSS when the dashboard is served over HTTPS.
- Command freshness, replay protection, per-junction authorization, rate limits, and operator audit/override controls require further implementation.
- Device credentials and endpoint addresses are deployment-specific and must not be committed as secrets.

## Before any controlled deployment

- [ ] Restrict network reachability to known devices; do not expose service ports directly to the internet.
- [ ] Implement strong device/service authentication and per-junction authorization.
- [ ] Use TLS for HTTP and WSS for WebSockets, with certificate verification.
- [ ] Add command expiry/nonces or sequence numbers and reject stale/replayed commands.
- [ ] Validate GPS bounds, timestamps, IDs, command duration, and direction at each boundary.
- [ ] Store secrets outside source control; rotate any credential that was ever committed.
- [ ] Review database permissions, retention, logging, backups, and location-data handling.
- [ ] Add rate limiting, monitoring, incident response, and operator/manual override procedures.
- [ ] Conduct bench and hardware-in-the-loop testing, independent safety review, and local regulatory approval.
- [ ] Demonstrate safe behavior during server, network, sensor, and power failures.

## Local development

CORS origins are configured with `RESCUEGRID_CORS_ORIGINS`, a comma-separated list of exact trusted origins. The default list is limited to common localhost development origins. Do not use wildcard CORS as a workaround for deployment issues.

These mitigations are a checklist, not a claim that the system is secure or safety certified.
