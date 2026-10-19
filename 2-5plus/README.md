# Sprint Airave 2.5+: root access and credentials

[Repository overview](../README.md) · [Original Airave 2.5 guide](../2-5/2-5.md)

A no-open access method was verified on the **Airave 2.5+**, HubBub-C1-600-RT, firmware **6.5.01.010**, hardware **750721.00.03**, FCC ID **QHYHUBBUBC4501-RT**. It uses a brief Telnet login window during startup, followed optionally by persistent access through the firmware's DEBUG_MODE boot flag. Other revisions are untested.

This unit serves **GoAhead-Webs/2.5.0** with **HTTP Digest authentication**. The original 2.5 script's HTTP Basic /setup.cgi method does not apply.

## 1. Connect to the LAN

Connect your computer to the femtocell's LAN Ethernet port. A USB Ethernet adapter works; use DHCP or an unused address in **192.168.17.0/24**. Verify the web interface at **http://192.168.17.1/**. The tested web login is **admin/admin**.

Use Python 3.10+; no external packages are required. All commands below assume you are in this repository's 2-5plus directory. Each live run of the bundled credential script requests a reboot, interrupting service.

## 2. Extract credentials during startup

```sh
python airave-plus-provision.py
```

The script requests a reboot through /goform/reboot, watches for Telnet on port 23, and attempts **root/root** during the short startup window. It reads the radio environment and raw environment partition before the startup firewall closes access.

A successful run saves **airave-plus-provision.txt** beside the script, containing:

```text
FEID=<device FEID>
IKE_GROUP_KEY=<device group key>
EAP_IDENTITY=<device identity including its domain>
EAP_PASSWORD=<device EAP password>
ACS_USERNAME=<device ACS username>
ACS_PASSWORD=<device ACS password>
```

It prints the saved path; read the file locally. Keep it private. The tested ACS username has the form **0005B9-cdmaFAP3-<FEID>**. Copy the actual extracted value into 1xBTS rather than relying on its original-model username default.

Supported options in the bundled version include:

```sh
python airave-plus-provision.py --host 192.168.17.1
python airave-plus-provision.py --web-user admin --web-password YOUR_WEB_PASSWORD
python airave-plus-provision.py --output private-fields.txt
python airave-plus-provision.py --command "id"
python airave-plus-provision.py --from-capture saved-raw-capture.txt --output parsed-fields.txt
```

The last command parses a previous **raw** capture offline. The normal six-field output is not a raw capture. --command saves command output instead of the six fields. A failed live attempt may save a .partial capture, which can contain secrets.

**Bundled-script limitation:** the copy currently in this repository collects credentials or executes a boot-window command. It does **not** automatically enable debug mode, print an SSH command, verify persistent access, or accept --no-debug. Those features were tested in a later script revision during the original investigation; the manual procedure below matches the version included here.

## 3. Optional persistent root access

The tested firmware honors **DEBUG_MODE=y** in the U-Boot **extra** variable. After enabling it and rebooting, LAN SSH port 22 and Telnet port 23 remained accessible, and HTTP on ports 80 and 8080 still worked. WAN access was not tested.

First record the current extra value privately:

```sh
python airave-plus-provision.py --command "fw_printenv extra" --output extra-before-debug.txt
```

Inspect the saved output. On the tested unit, extra was originally undefined. **Only when extra is undefined or empty**, use:

```sh
python airave-plus-provision.py --command "fw_setenv extra 'DEBUG_MODE=y'; sync; fw_printenv extra" --output debug-setting-result.txt
```

If extra already contains other boot arguments, preserve every existing token, replacing only any DEBUG_MODE token with DEBUG_MODE=y. Pass that complete value to fw_setenv extra instead of the simple command above. Do not replace unrelated boot arguments. Keep a record of the original value for rollback.

Read debug-setting-result.txt and confirm **extra=DEBUG_MODE=y**, or the preserved argument list containing DEBUG_MODE=y. This invocation reboots **before** executing the command; the newly written flag takes effect on the **next** boot. After confirming the write completed, reboot through the web interface and let normal startup finish.

Verify persistent access after startup with the SSH command below, then run su and id. Root should report uid=0. A successful boot-window command alone does not verify persistence. No startup-file edit or replacement Telnet daemon is needed for this method.

### Windows SSH

Use ACS_USERNAME from the credential file in place of YOUR_ACS_USERNAME:

```powershell
ssh -p 22 -o KexAlgorithms=+diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa -o MACs=+hmac-sha1 -o PreferredAuthentications=password -o PubkeyAuthentication=no YOUR_ACS_USERNAME@192.168.17.1
```

Enter **ACS_PASSWORD** at the SSH password prompt, then:

```sh
su
id
```

The tested su password is **root**. Accept a host key only after checking it for your own unit; a fingerprint from another femtocell is not transferable. Unlike the original 2.5, the Plus uses direct radio SSH on **22**, not the 23022 router relay.

### Undo persistent debug mode

From an established root shell, restore extra to its exact recorded value, then run sync and reboot. If extra was originally undefined, the rollback is:

```sh
fw_setenv extra
sync
reboot
```

Deleting extra is appropriate only when it was originally absent. Otherwise restore the full original value. Normal startup will close the debug access path again. Credential extraction through the boot window and persistent debug access are separate from the OTASP installer.

## 4. Enroll in 1xBTS

Use the [shared credential mapping](../README.md#extract-the-device-credentials) and upstream [femtocell setup guide](https://1xbts.org/docs/guides/femtocells/). Select the **airave-25plus** profile.

The tested Plus requires an explicit IPv4 netmask attribute in the IKE configuration response.

If you change away from the default /24 IP pool, you will have to add this in your femto.local.json at the top level, and change it to refelct your new IP pool.

```json
{
  "segw": {
    "vip_netmask": "255.255.255.0"
  }
}
```
Without it, the Plus authenticated and received a virtual IP but immediately deleted its ESP tunnel. Existing original 2.5 tunnels also worked with the mask present in the tested setup.

The unmodified airave-25-2x profile also provisioned the Plus during an in-place comparison with the netmask supplied. However, its legacy per-PDSN status queries returned **9005 Invalid Parametername**. The Plus profile omits unsupported queries such as OneXpdsnAdminStatus and OneXpdsnHealthStatus. That improves status collection; it does not establish packet-data compatibility.

## Radio capabilities

**Normal service on the tested Plus is BC1 / 1900 MHz PCS. Its 800 MHz capability is a separate BC0/BC10 beacon system.** The beacon can advertise discovery/redirection signaling, but it does not provide a complete two-way 800 MHz traffic carrier. A BC0-only handset cannot follow a redirect to a BC1 service carrier.

In the investigation:

- The service-sector firmware rejected BC0/777 and BC10/476; BC1/725 and BC1/1175 were accepted.
- An SDR confirmed BC0/777 beacon bursts at **893.310 MHz** with a requested 0 dBm, and confirmed disappearance after disable. This established beacon RF output, not calls on BC0.
- The beacon was later disabled. The Plus profile does not automatically configure or enable those experimental beacon settings.
- IPsec, ACS, SIP registration, GPS/timing lock, and BC1 on-air state were verified. These checks alone do not establish ordinary handset voice/SMS, 1x packet data, or EV-DO service.

Root access and OTASP patches do not remove the PCS service limitation. The local 1xBTS checkout's docs/FEMTOCELLS.md contains the longer investigation and references.

## 5. Optional OTASP patch

The [Plus installer](OTASP_Patch_Installer_2-5plus.sh) supports **OneXApplication 6.5.01.010** with this exact SHA256:

```text
f813ef587992b85a2f8cbf3da9197a596d4360b10fc1bb947466cfa503e188db
```

Transfer OTASP_Patch_Installer_2-5plus.sh to the Plus as **/tmp/airvana25plus-otasp.sh**. The renamed destination matches the [full installer instructions](OTASP_Patch_README_2-5plus.md). Become root, then:

```sh
sh /tmp/airvana25plus-otasp.sh install
sh /conf_files/otasp25plus/airvana25plus-otasp.sh status
sh /conf_files/otasp25plus/airvana25plus-otasp.sh check
```

The installer embeds its PowerPC helper, verifies the executable hash, starts the watcher immediately, and creates persistent module hooks. It reapplies six RAM patches to each new application process without changing the firmware executable. It requires the matching 1xBTS OTASP transport changes.

The recorded Plus test completed a Convoy OTASP session with a **6,836-byte PRL readback and valid CRC**, NAM readbacks, and successful commit. Subscriber downloads were disabled; this does not validate downloading a new subscriber configuration.

To stop automatic patching and restore current RAM instructions:

```sh
sh /conf_files/otasp25plus/airvana25plus-otasp.sh restore
```

To restore and remove the installation:

```sh
sh /conf_files/otasp25plus/airvana25plus-otasp.sh uninstall
```

The disable action alone leaves current RAM patches active. Read the full installer instructions for recovery and logs. Do not use the original 2.5 installer on the Plus.

## Troubleshooting

| Symptom | Meaning / next check |
| --- | --- |
| /setup.cgi returns 404 | Expected on this Plus; use the Digest-authenticated Plus script. |
| Telnet did not open during boot | Check LAN reachability, web credentials, firmware, and reboot behavior. The bundled script watches for 70 seconds. |
| Root command did not complete in the boot window | Inspect any private .partial capture; confirm uid=0 and command completion before trusting results. |
| SSH closes after normal startup | Check that DEBUG_MODE=y was written and a subsequent reboot occurred. |
| IKE established but no usable data tunnel | Check vip_netmask, the running generator version, and a fresh negotiation. |
| CWMP 9005 on per-PDSN status | Use the Plus profile's supported status queries; this is not proof of a PDSN service failure. |
| Plus missing from dashboard after adding it | Restart femto-core; the tested version captures that list at startup. |
