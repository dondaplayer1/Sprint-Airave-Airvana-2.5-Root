# Airvana OTASP startup patch — 1.0.1

One file to upload: **airvana-otasp.sh**. It embeds a static PowerPC helper and all six verified RAM patches. It needs no Python, compiler, package manager, base64 decoder, or connection to 1xBTS to apply patches.

## Supported device

Tested on this Airvana Airave 2.5 firmware: OneXApplication **5.0.02.094, build 913922000**, Linux 2.6.21.7, PowerPC 32-bit big-endian.

Required executable SHA256:

    8a894315f36def0791e266e966fbd1726bd97c797831dd0db932b516a27b5030

Other firmware is refused. This is a device companion to the 1xBTS OTASP transport fixes; installing it alone does not add those server-side fixes.

## Install over SSH or telnet

Transfer airvana-otasp.sh to /tmp/airvana-otasp.sh, log in, and become root with su. Then run:

    sh /tmp/airvana-otasp.sh install

If you serve the downloaded file from a computer on your LAN, the Airvana's wget can fetch it from that computer before installation. The installer itself downloads nothing.

Installation enables and starts the watcher immediately. No reboot is required to apply the patches. The installer saves itself and its helper under /conf_files/otasp/ and adds /etc/sysconfig/modules/airvana-otasp.modules, a new executable boot hook. Re-running install updates the files without adding duplicate hooks.

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