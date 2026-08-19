# Security and data boundaries

## Never commit

- Cloudflare Tunnel tokens, API tokens or Access service credentials.
- AWS access keys, session credentials or private certificates.
- ShellHub credentials or SSH private keys.
- Raw camera footage, identifiable-person imagery, or unreviewed captures.
- Large model binaries.

## Private storage rule

S3 remains private with Block Public Access enabled. The Pi uploads selected
event media through a device-specific, least-privilege path using short-lived
credentials or presigned URLs. The browser receives short-lived signed links
from an authenticated service; it never receives long-lived AWS credentials.

## Retention and sharing

Select and retain data deliberately. Define retention before collecting
person-related imagery, provide authorized access only, and record why a
frame was retained. Demo viewers receive Cloudflare Access, not direct S3
links or Pi access.
