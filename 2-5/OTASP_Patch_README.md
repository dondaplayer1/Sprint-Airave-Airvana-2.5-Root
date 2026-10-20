# Airvana Airave 2.5 OTASP startup patch — 1.0.1

One file to upload: **OTASP_Patch_Installer.sh**. It embeds a static PowerPC helper and all six verified RAM patches. It needs no Python, compiler, package manager, base64 decoder, or connection to 1xBTS to apply patches.

## Supported device

Tested on this Airvana Airave 2.5 firmware: OneXApplication **5.0.02.094, build 913922000**, Linux 2.6.21.7, PowerPC 32-bit big-endian.

Required executable SHA256:

    8a894315f36def0791e266e966fbd1726bd97c797831dd0db932b516a27b5030

Other firmware is refused. This is a device companion to the 1xBTS OTASP transport fixes; installing it alone does not add those server-side fixes.

**For the original 2.5 only.** The 2.5+ has different firmware and needs the [**2.5+ installer**](../2-5plus/OTASP_Patch_Installer_2-5plus.sh). The installers are not interchangeable.

## The problem these patches solve

Airave firmware already contains OTASP-related code, but that does not mean it reliably completes an OTASP session with 1xBTS. In the tested setup, dialing `*228` establishes a voice-service call (service option 3), and the provisioning protocol then exchanges OTA Data Burst messages on that call's traffic channel.

The stock firmware could queue the network's OTA message without dispatching it on the active voice-call path. The phone would never receive the request, so 1xBTS could time out waiting for a Protocol Capability response. A phone could show **Programming in progress**, followed by **Programming failed** or **Service Update Failed**. Those symptoms can also have server-side causes; the installer addresses the firmware defects below.

After getting the first exchange moving, additional queue and sequence-number defects could stall later messages. The patches therefore address the whole exchange rather than only making the first request leave the queue.

## What the RAM patches change

| Fix | Stock behavior found during testing | What the patch does |
| --- | --- | --- |
| **Send OTA bursts during an active voice call** | OTA data could be queued without invoking the existing sender in the voice-service path. | Adds a narrowly scoped dispatch path that calls the firmware's existing OTA send routine for the active voice-call case, while retaining its call-clearing checks. It does not force the call to service option 18. |
| **Clear stale, unsent queue data** | A stale unsent entry could remain in the same voice-call queue and interfere with subsequent provisioning bursts. | Removes that stale queue entry under the checked voice-call conditions so later requests can progress. |
| **Use the complete forward sequence range** | The forward sequence logic treated `7` as its limit/sentinel instead of allowing the complete three-bit range. | Corrects the limit/sentinel to `8`, allowing sequence values `0` through `7` and the subsequent wrap to `0`. |
| **Accept acknowledgment sequence 7** | The acknowledgment path rejected `7`, even though it is a valid three-bit sequence value. | Accepts ACK values `0` through `7`; `8` remains outside the valid range. This avoids a stall when an exchange reaches sequence 7. |

These are **four logical fixes implemented in six memory regions**: two dispatch/cleanup hooks, their two short helper routines, and two sequence/acknowledgment instruction changes. The embedded payload is a small executable patch helper and its patch definitions, **not a full firmware or memory dump**.

## What the installer adds beyond the RAM fixes

The RAM changes alone disappear when `OneXApplication` exits or the device reboots. The installer adds a persistent startup hook and a watcher that reapplies the same verified patches to each new process instance. It also provides firmware checks, live-region verification, status reporting, and restore/uninstall commands.

**Persistence means automatic reapplication, not a rewritten firmware image.** `/usr/bin/OneXApplication` is left unchanged on disk. 

## The 1xBTS changes are still required

This is the **device-side half** of the fix. The corresponding 1xBTS changes must also be present:

- Encode and translate A1 ADDS Deliver and ADDS Deliver Ack messages through the femto/SIP interface.
- Answer the SIP call and receive its ACK before sending the first OTA request.
- Handle the Airvana's validated legacy OTA message format and its delivery acknowledgments carried in SIP INFO.
- Route standalone SIP MESSAGE replies back to the correct handset, call, and femtocell. This also matters when a handset has a simultaneous packet-data call leg.

In the implementation developed with these installers, those changes live in `crates/cdma-ios/src/femto_interface_msg.rs`, `crates/cdma-femto/src/fcs.rs`, and `crates/cdma-femto/src/sip.rs`. Installing this script does not install or update any of those server files.

The MSC still decides which NAM/MDN/PRL blocks to read or write. Enable only the desired `otasp.writes` options in the 1xBTS configuration and select the intended PRL. A successful session with writes disabled validates the protocol exchange; it does not prove a new PRL or subscriber configuration was downloaded.

## Install over SSH or telnet

Transfer `OTASP_Patch_Installer.sh` to `/tmp/OTASP_Patch_Installer.sh`, log in, and become root with su. Then run:

    sh /tmp/OTASP_Patch_Installer.sh install

If you serve the downloaded file from a computer on your LAN, the Airvana's wget can fetch it from that computer before installation. The installer itself downloads nothing.

Installation enables and starts the watcher immediately. No reboot is required to apply the patches. The installer saves itself and its helper under /conf_files/otasp/ and adds /etc/sysconfig/modules/airvana-otasp.modules, a new executable boot hook. Re-running install updates the files without adding duplicate hooks.

The uploaded filename differs from the installed script name. The management commands below deliberately use the installed path. Applying, checking, or restoring live patches briefly stops the radio application's threads; perform those operations while the unit is idle.

## Check and remove

    sh /conf_files/otasp/airvana-otasp.sh status

Status reports watcher state and its last result without attaching a debugger. To inspect all six live memory regions directly:

    sh /conf_files/otasp/airvana-otasp.sh check

Disable future automatic patching:

    sh /conf_files/otasp/airvana-otasp.sh disable

Disable and restore the current process's original instructions:

    sh /conf_files/otasp/airvana-otasp.sh restore

Enable automatic patching again:

    sh /conf_files/otasp/airvana-otasp.sh enable

Remove the startup hook, restore current RAM patches, and delete the installed script/helper:

    sh /conf_files/otasp/airvana-otasp.sh uninstall

Uninstall removes the added module hook and leaves stock startup scripts unchanged. Any backup retained from earlier experiments is left in place. Stop/disable alone leaves existing RAM patches active until restore or application restart.

## Behavior

The watcher polls every five seconds and identifies each OneXApplication instance by PID and kernel start time. It verifies the full executable SHA256 before attaching. The helper uses the firmware's existing gdbserver, bound only to 127.0.0.1:23452, to stop the application threads, validate every patch region, write and read back the changes, and detach. An existing debugger causes refusal. No permanent debugger listener is left running.

All regions must contain known original instructions, the installed patch, or zeroes in the two reserved code caves. Validation of all six regions precedes every write. Caves are written before branches. Write failure triggers restoration of the pre-transaction memory snapshots. Refused or failed instances are logged once rather than repeatedly attached; inspect and resolve the cause before restarting the watcher.

Logs and state live in RAM: /tmp/airvana-otasp.log, /tmp/airvana-otasp.state, /tmp/airvana-otasp-gdb.log, and /tmp/airvana-otasp-start.log. Operational logs rotate at approximately 32 KiB. The script and hook survive normal reboot. Although /etc points into /conf_files/etc_rw, early /init overwrites stock files there from the firmware template on every boot. The installer therefore adds a new .modules file, which that overlay preserves; the existing rc.sysinit module loop executes it. It does not edit stock rcS. Factory resets and firmware upgrades may require reinstallation and firmware-specific support.

The OneXApplication firmware file is not modified. The patches are reapplied to RAM on each new process. Subscriber programming policy remains in 1xBTS configuration.

## Recovery

To prevent application of patches at the next boot, create /conf_files/otasp/disabled as root. Use the restore command to also remove the active RAM patches. If a live restore fails, the installer retains its files and disabled flag for inspection; restart OneXApplication only after investigating the reported error.

## Validation

Verified on the lab unit: PowerPC execution, SHA256 self-test, full firmware hash, refusal of an unsupported executable, all six live patch regions, clean debugger detach, RAM restore and reapplication, uninstall/reinstall, and repeated installation with one hook.

Full reboot result is recorded in the accompanying validation note.