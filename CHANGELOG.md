# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-18

### Added

- Async UDP client with typed, batched status and fan settings reads.
- Reply validation for sender address, device ID, checksum, and register set.
- Signed temperatures and filter countdowns, with unsupported values represented as missing.
- Write confirmation by device echo or register readback, including after a reply timeout.
- Filter reset and bounded hostname resolution.

[0.1.0]: https://github.com/voluzi/aiovents/tree/v0.1.0
