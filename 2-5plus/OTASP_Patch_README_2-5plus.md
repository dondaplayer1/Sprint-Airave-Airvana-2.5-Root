# Airvana Airave 2.5+ OTASP startup patch — 1.0.0

Upload only **OTASP_Patch_Installer_2-5plus.sh**. This separate installer supports **OneXApplication 6.5.01.010** on the Airvana Airave 2.5+.

Required firmware SHA256:

    f813ef587992b85a2f8cbf3da9197a596d4360b10fc1bb947466cfa503e188db

Other firmware is refused. Use `../2-5/OTASP_Patch_Installer.sh` for the original 2.5 running 5.0.02.094. The Plus script does not modify that installer.

**For the 2.5+ only.** This is a separate firmware-specific port of the same logical fixes. Its patch addresses, helper, and startup hook differ from the [**original 2.5 installer**](../2-5/OTASP_Patch_Installer.sh); do not install both packages on one unit.

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

**Persistence means automatic reapplication, not a rewritten firmware image.** `/usr/bin/OneXApplication` is left unchanged on disk. This package is an OTASP compatibility fix; it does not add new band support, enable EVDO or packet data, change transmit power, fix GPS/timezone behavior, or change subscriber programming values.

## The 1xBTS changes are still required

This is the **device-side half** of the fix. The corresponding 1xBTS changes must also be present:

- Encode and translate A1 ADDS Deliver and ADDS Deliver Ack messages through the femto/SIP interface.
- Answer the SIP call and receive its ACK before sending the first OTA request.
- Handle the Airvana's validated legacy OTA message format and its delivery acknowledgments carried in SIP INFO.
- Route standalone SIP MESSAGE replies back to the correct handset, call, and femtocell. This also matters when a handset has a simultaneous packet-data call leg.

In the implementation developed with these installers, those changes live in `crates/cdma-ios/src/femto_interface_msg.rs`, `crates/cdma-femto/src/fcs.rs`, and `crates/cdma-femto/src/sip.rs`. Installing this script does not install or update any of those server files.

The MSC still decides which NAM/MDN/PRL blocks to read or write. Enable only the desired `otasp.writes` options in the 1xBTS configuration and select the intended PRL. A successful session with writes disabled validates the protocol exchange; it does not prove a new PRL or subscriber configuration was downloaded.

## Install

Copy `OTASP_Patch_Installer_2-5plus.sh` to `/tmp/OTASP_Patch_Installer_2-5plus.sh` over SSH or through a LAN download from a telnet shell. Become root, then run:

    sh /tmp/OTASP_Patch_Installer_2-5plus.sh install

The installer downloads nothing and needs no Python, compiler, external helper download, or gdbserver. It embeds a static PowerPC helper, checks the extracted payload checksum before executing it, verifies the full firmware hash, and tests thread stop/resume on a disposable process before enabling automatic patching.

Installation immediately starts the watcher. Reboot is not required to apply patches. The watcher detects each new OneXApplication instance by PID and start time and reapplies all six patches to RAM.

The uploaded filename differs from the installed script name. The management commands below deliberately use the installed path. Applying, checking, or restoring live patches briefly stops the radio application's threads; perform those operations while the unit is idle.

## Status and removal

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh status

To independently check all six live patch regions:

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh check

To disable future automatic patching (current RAM patches remain):

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh disable

To disable and also restore the running process's original instructions:

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh restore

To enable again:

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh enable

To restore RAM and remove the script, helper, and both boot-hook copies:

    sh /conf_files/otasp25plus/airvana25plus-otasp.sh uninstall

## What persists

The installed script and helper live in /conf_files/otasp25plus/.

This firmware rebuilds /etc in RAM from /etc_rw during boot. The installer therefore adds a new executable hook at /etc_rw/sysconfig/modules/airvana25plus-otasp.modules and its runtime copy at /etc/sysconfig/modules/airvana25plus-otasp.modules. The existing rc.sysinit module loop runs the hook at boot. No stock startup script is edited. Installation requires writable /etc_rw, as verified on the tested unit.

The OneXApplication firmware file remains unchanged. RAM patches are reapplied automatically after reboot or application restart. Firmware upgrades or factory resets can remove the installer or hook and require reinstallation.

## Verification and recovery

The helper uses legacy ptrace to stop every radio thread, confirm the known instructions in all six regions, apply and read back the patches, then detach all traced threads. The PowerPC kernel handles instruction-cache synchronization for these writes. There is no debugger listener or permanent network service.

Unknown firmware, unexpected instructions, an existing tracer, or a failed thread stop causes refusal. Failed writes trigger restoration of the transaction's original memory snapshots. A failed process instance is not repeatedly attached; resolve the logged issue before restarting the watcher.

Logs are in RAM:

- /tmp/airvana25plus-otasp.log
- /tmp/airvana25plus-otasp-start.log
- /tmp/airvana25plus-otasp.state

Create /conf_files/otasp25plus/disabled to prevent future automatic application. Use restore to also remove active RAM patches.

BusyBox 1.11 on this unit drops leading NUL bytes when decoding a percent-b argument. The installer uses direct octal printf formats instead and verifies the embedded helper's checksum before execution.

## OTASP prerequisites and scope

The corresponding 1xBTS ADDS/SIP OTASP changes are still required. The Plus also requires the configured virtual-IP netmask to be included by the SeGW config generator. On the test stack, recreating a stale femto-segw-config container from the updated image restored that support.

The six patches completed a Convoy OTASP session through this Plus: 6,836-byte PRL readback with valid CRC, NAM readbacks, and successful commit. That session had subscriber downloads disabled. This installer does not change subscriber provisioning policy or radio configuration.

Installer boot validation is recorded in the accompanying validation note. Sources and rebuild instructions are available in the source package; the embedded musl runtime's license notices are included in the script.
