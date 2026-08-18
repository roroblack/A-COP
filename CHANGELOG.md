# Changelog

All notable changes to the `basement` package are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versions follow [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-08-18

### Added

- Composer write channel v2 with short-lived HMAC JWTs and separated
  `composer:read`, `composer:validate`, and `composer:write` scopes.
- Response Generation & Review Team (DoD-29), including deterministic review
  for prohibited terms, factual grounding, PII, and rule-based tone selection.
- Regression coverage for expired and forged Composer JWTs.

### Changed

- Billing/Subscription and Technical/Entitlement Teams were moved to
  `examples/` and removed from production routing/configuration while their
  example implementations remain available to evaluation.
- Composer audit output is injectable through application state, preventing
  test runs from writing to the repository's live audit path.

### Fixed

- A failure during the `CLASSIFIED` state transition is no longer reported as
  `classification_failed`; classifier failures and transition failures retain
  their distinct meanings.

The entries above are summarized from commits `c1b1a4a`, `17253ff`, `807bd2c`,
and `be298c7`.

## [0.1.0]

Initial `basement` version recorded in the package metadata. This section is a
historical baseline only; the repository has no earlier versioned changelog or
release tag from which to reconstruct a more detailed change list.

[0.2.0]: https://github.com/roroblack/A-COP/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/roroblack/A-COP/releases/tag/v0.1.0
