# Airvana OTASP investigation

Verified October 18, 2026 at 8:08 p.m. America/New_York: Convoy completed *228. MSC outcome Committed, commit result 0x00. Full PRL 6836 bytes read with valid CRC; NAM readbacks completed. Subscriber write flags were left disabled; this validates the protocol exchange and commit, not a new subscriber configuration download.

## Causes and corrections

- 1xBTS lacked ADDS Deliver/ACK conversion and correct standalone handset routing for the Airvana.
- The outgoing SIP call needed to be answered and ACKed before the first provisioning burst.
- Airvana53/54 uplinks omit the discriminator. Compatibility parsing now accepts only validated legacy OTA payloads and tagged acknowledgements.
- Airvana returns delivery ACKs in SIP INFO. These now route to the MSC with same-FAP, outstanding-tag validation.
- The Airvana firmware queued OTA bursts without dispatching them during a voice call. A RAM patch invokes its existing send routine and removes stale unsent queue entries.
- Its dedicated-channel assured sequence allocator used seven values, skipping 7; its reverse ACK path also skipped 7. The verified RAM correction uses eight values and accepts ACK 7. The diagnostic trace showed repeated successful wraps through 7 after this correction.

## Current state

1xBTS source: /home/xxx/1xbts on xxx.xxx.xxx.xxx. Origin is xxx/xxx; original source remote is upstream. Three Rust files have uncommitted changes. 149 femto tests passed, one preexisting test ignored; 28 IOS tests previously passed. Format and diff checks passed.

Airvana xxx.xxx.xxx.xxx: RAM fixes are active in OneXApplication PID1654. No firmware file or boot scripts were changed. Application restart or device reboot removes the firmware fixes. The accompanying JSON records the exact firmware hash, original bytes, and replacement bytes for review/reproduction. Apply only to this exact firmware after checking live memory. Temporary sequence recorder was removed and debugger detached.

Runtime tools and rollback backups remain in the local work directory. fap_memory_patch.py supports rollback for dispatch/queue changes and wrapoff for the sequence correction. These local diagnostic helpers contain device access details and are intentionally excluded from this deliverable. No source commit or push was made. Other femtocell configuration and subscriber write flags were not changed.
