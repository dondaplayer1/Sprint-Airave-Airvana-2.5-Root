# Sprint Airave 2.5: root access and credentials

[Repository overview](../README.md) · [Airave 2.5+ guide](../2-5plus/2-5PLUS.md)

This guide is for the **original Airave 2.5**, whose router exposes /setup.cgi. The script uses a diagnostics ping command injection to open LAN access and forward connections to the separate internal radio. The Plus uses a different web interface and needs its own script.

## 1. Connect to the LAN

Connect your computer to the Airave's LAN Ethernet port. Obtain an address by DHCP and check that **192.168.17.1** is reachable. The script defaults to that address and source subnet **192.168.17.0/24**. It uses the default web credentials **admin/admin** when challenged with HTTP Basic authentication.

Use Python 3.10+; no pip packages are required. Run the following from this repository's 2-5 directory, on Windows or Linux:

```sh
python airave-provision.py
```

The tool performs five unlock steps:

1. Allows LAN access to the host's Telnet and HTTPS ports.
2. Enables IP forwarding.
3. Removes the blackhole route to the internal radio, 192.168.255.2.
4. Forwards LAN TCP 23022 to radio SSH port 22.
5. Forwards LAN TCP 23023 to radio Telnet port 23.

It reads the host identity with cmld_client, logs into the radio, becomes root when needed, and collects credentials from its environment and configuration. Masked environment values are supplemented from the raw environment partition.

To use a different management address or source subnet:

```sh
python airave-provision.py --host 192.168.17.1 --lan 192.168.17.0/24
```

Replace those example values with your actual network. The source subnet matters for the forwarding rules. The internal radio addresses remain fixed in the script.

## 2. Save the six fields

Successful output includes:

```text
FEID=<device FEID>
IKE_GROUP_KEY=<device group key>
EAP_IDENTITY=<device identity including its domain>
EAP_PASSWORD=<device EAP password>
ACS_USERNAME=<device ACS username>
ACS_PASSWORD=<device ACS password>
```

It also prints an SSH command, the radio login password, and the instruction to use **su**, password **root**. Save output privately if needed:

```sh
python airave-provision.py > airave-provision-private.txt
```

Progress goes to stderr. The output file contains secrets. The script's --json option emits a JSON object followed by SSH instructions, so its complete stdout is **not** a standalone JSON document.

## 3. Open a radio root shell

Use the exact SSH command and password printed by the script. The original unit's username normally has this form:

```text
0005B9-cdmaFAP-<FEID>
```

A Windows OpenSSH command template is:

```powershell
ssh -p 23022 -o KexAlgorithms=+diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa -o Ciphers=+aes128-cbc,aes256-cbc,3des-cbc -o MACs=+hmac-sha1 -o PreferredAuthentications=password -o PubkeyAuthentication=no YOUR_RADIO_USERNAME@192.168.17.1
```

Replace YOUR_RADIO_USERNAME with the printed username. Use the printed radio password, then:

```sh
su
id
```

Enter **root** at the su password prompt. Confirm id reports uid=0. The host's port 23 and radio relay port 23023 are different shells; install radio-specific patches on the **radio**.

The unlock script changes runtime firewall/forwarding state. It does not install a persistent router unlock. After a reboot, rerun the normal script to recreate access. Use --skip-unlock only when the relays already exist; repeatedly adding rules during the same boot can create duplicates.

## 4. Configure 1xBTS

Map the six fields using the [shared credential table](../README.md#extract-the-device-credentials). Choose the profile for the radio firmware, rather than inferring it from the product label:

| Original firmware | 1xBTS profile |
| --- | --- |
| 2.x | airave-25-2x |
| 5.x | airave-25-5x |

Follow the upstream [femtocell setup guide](https://1xbts.org/docs/guides/femtocells/) for the core and DNS configuration. Keep your site credentials in config/femto.local.json. Check IPsec, ACS, and SIP before handset testing.

## 5. Optional OTASP support

The supplied installer supports **OneXApplication 5.0.02.094, build 913922000** only, with SHA256:

```text
8a894315f36def0791e266e966fbd1726bd97c797831dd0db932b516a27b5030
```

Transfer [OTASP_Patch_Installer.sh](OTASP_Patch_Installer.sh) to the **radio** as **/tmp/airvana-otasp.sh**. This rename matches the installed script name used in the [OTASP instructions](OTASP_Patch_README.md). Become root, then run:

```sh
sh /tmp/airvana-otasp.sh install
sh /conf_files/otasp/airvana-otasp.sh status
sh /conf_files/otasp/airvana-otasp.sh check
```

Installation starts the watcher immediately and adds a boot hook. The firmware file stays unchanged; the watcher patches each new application process in RAM. Matching 1xBTS ADDS/SIP OTASP changes are required as well.

To disable automatic patching and restore the current process:

```sh
sh /conf_files/otasp/airvana-otasp.sh restore
```

To restore and remove the installation:

```sh
sh /conf_files/otasp/airvana-otasp.sh uninstall
```

Read the full OTASP instructions for checks, logs, and recovery. The disable command alone leaves current RAM patches active.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| /setup.cgi returns 404; web server uses Digest authentication | Check whether this is a Plus and use the Plus guide. |
| Web authentication fails | The bundled script expects admin/admin; changed credentials require adapting it. |
| Radio relay times out | Verify the LAN subnet and all five unlock steps; rerun after a reboot. |
| Missing or masked credential fields | Preserve the error privately and report the firmware revision; do not substitute another unit's values. |
| SSH rejects the connection | Use port 23022 and the command printed by the script, including legacy algorithms. |
| Access disappeared after reboot | Recreate the runtime unlock. This is separate from the OTASP watcher's persistence. |
