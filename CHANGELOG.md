# Changelog

## 0.1.0

- Add an asynchronous Vents AHU client with batched status and fan settings reads.
- Verify reply sender, device ID, checksum, and exact register set.
- Decode signed temperatures and filter countdowns and expose unsupported values as missing.
- Verify compact writes and read back on an unconfirmed echo or reply timeout. The reference
  sync client does not read back on timeout.
- Support filter reset.
