# Airave 2.5+ OTASP installer — 1.0.0

Upload only **airvana25plus-otasp.sh**. This separate installer supports **OneXApplication 6.5.01.010** on the Airvana Airave 2.5+.

Required firmware SHA256:

    f813ef587992b85a2f8cbf3da9197a596d4360b10fc1bb947466cfa503e188db

Other firmware is refused. Use the original airvana-otasp.sh for the original 2.5 running 5.0.02.094. The Plus script does not modify that installer.

## Install

Copy this one file to /tmp/airvana25plus-otasp.sh over SSH or through a LAN download from a telnet shell. Become root, then run:

    sh /tmp/airvana25plus-otasp.sh install

The installer downloads nothing and needs no Python, compiler, external helper download, or gdbserver. It embeds a static PowerPC helper, checks the extracted payload checksum before executing it, verifies the full firmware hash, and tests thread stop/resume on a disposable process before enabling automatic patching.

Installation immediately starts the watcher. Reboot is not required to apply patches. The watcher detects each new OneXApplication instance by PID and start time and reapplies all six patches to RAM.

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
