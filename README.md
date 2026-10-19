# Sprint Airave / Airvana 2.5 and 2.5+

Guides and tools for obtaining root access to Sprint Airvana Airave femtocells, extracting their SeGW and ACS credentials, and using them with [1xBTS](https://github.com/chrismoos/1xbts).

These are two different access paths. Start with the guide for your device; the same HubBub model name can appear on different hardware.

| Device | Start here | Access method | Radio SSH port |
| --- | --- | --- | --- |
| Airave 2.5 (original) | [2.5 guide](2-5/2-5.md) | Router diagnostics command injection, then forwarding to the internal radio | 23022 |
| Airave 2.5+ (Plus) | [2.5+ guide](2-5plus/2-5PLUS.md) | Brief root Telnet window during boot; optional persistent debug mode | 22 |

The tested Plus reports firmware **6.5.01.010**, hardware **750721.00.03**, and FCC ID **QHYHUBBUBC4501-RT**. Results on other revisions may differ. The original 2.5 OTASP patch specifically targets **5.0.02.094**; that patch requirement is separate from the rooting script's compatibility.

## AI Use Disclosure

Artificial Intelligence models from OpenAI (Codex w/ GPT-6.1 Sol & Daybreak GPT-6 Luna) were used to conduct significant research of these femtocells, as well as developing helper scripts and patches, and writing documentation for use with 1xBTS.

AI-generated material can contain mistakes. Review any scripts/patches before running them, and double-check firmare and hardware requirements. Results verified on tested units may not apply to other devices running different firmware versions.

## Responsible Use and RF Transmission

This repository is intended for research and experimentation with equipment you own or are explicitly authorized to administer. Never attempt to access, modify, or extract credentials from devices, systems, or networks without authorization. Possessing a device or its credentials does not authorize access to a carrier’s network.

Radio transmission is strictly at your own risk. You are responsible for obtaining any required licenses or permissions, complying with applicable laws and regulations, and preventing harmful interference. Owning a femtocell does not grant permission to transmit on its supported frequencies. Use an appropriately shielded or conducted RF test setup where transmission is not authorized.

These tools and instructions are provided without warranty. You assume responsibility for their use, including equipment damage, service disruption, unauthorized access, and interference.

## What is included

- [Original 2.5 credential script](2-5/airave-provision.py) and [Plus credential script](2-5plus/airave-plus-provision.py).
- Separate firmware-specific OTASP installers and instructions for [2.5](2-5/OTASP_Patch_README.md) and [2.5+](2-5plus/OTASP_Patch_README_2-5plus.md).
- [OTASP investigation notes](misc-docs/airvana-otasp-findings.md). These describe an earlier manual-patching stage; use the installer guides for current persistence and removal instructions.

Root access, 1xBTS enrollment, and OTASP support are separate steps. The OTASP installer is optional for initial enrollment and requires matching server-side OTASP support.

## Before starting

Use a device you own or are authorized to administer. Connect your computer to its **LAN** Ethernet port; the default address used here is **192.168.17.1**. Use DHCP, or an unused address in 192.168.17.0/24 if necessary. A USB Ethernet adapter is convenient but not required. Avoid another active network with the same subnet.

You need Python 3.10+ for the bundled scripts and an SSH client for an interactive radio shell. The Python tools use only the standard library. Keep the management LAN trusted: these devices use old SSH algorithms and Telnet. Keep extracted credentials, raw captures, environment backups, and local 1xBTS configuration out of public commits. Operate the radio only where you have authorization to transmit.

## Extract the device credentials

Follow the appropriate model guide. Both scripts produce these six fields:

| Extracted field | Destination within a 1xBTS site |
| --- | --- |
| FEID | feid |
| IKE_GROUP_KEY | segw.ike_group_key |
| EAP_IDENTITY | segw.eap_identity |
| EAP_PASSWORD | segw.eap_password |
| ACS_USERNAME | acs.username |
| ACS_PASSWORD | acs.password |

These are device credentials, not values to invent. The six-field output does not include a separately named SIP password; obtain or configure that value according to the selected 1xBTS device profile. Preserve the explicit ACS username: the tested Plus uses **cdmaFAP3**, while the original uses **cdmaFAP**.

## Configure in 1xBTS

Use the upstream [femtocell setup guide](https://1xbts.org/docs/guides/femtocells/) for the complete core, routing, DNS, and handset setup. This repository covers device access and model-specific findings.

## Plus radio limitation

The tested Plus provides normal service on **BC1 / 1900 MHz PCS**. Its **BC0/BC10 800 MHz transmitters are beacons**, used for discovery/redirection. An 800 MHz beacon is not an 800 MHz traffic carrier for calls, SMS, or data. Rooting and installing the OTASP patch do not change that distinction. See the [Plus findings](2-5plus/2-5PLUS.md#radio-capabilities).

## Optional OTASP patches

| Device | Firmware | Installer in this repository |
| --- | --- | --- |
| Original 2.5 | OneXApplication 5.0.02.094, build 913922000 | [OTASP_Patch_Installer.sh](2-5/OTASP_Patch_Installer.sh) |
| 2.5+ | OneXApplication 6.5.01.010 | [OTASP_Patch_Installer_2-5plus.sh](2-5plus/OTASP_Patch_Installer_2-5plus.sh) |

The installers enforce exact executable hashes. They apply six patches to the running application's RAM and install a watcher to reapply them after restart; they leave the firmware executable unchanged. Do not interchange the installers or bypass their firmware checks. Each model guide explains the filename used when transferring the installer.

## Reporting results

Include the model, FCC ID, firmware revision, script/version used, and the failing stage. Redact passwords, device identities, and private configuration before sharing logs. Distinguish credential extraction, persistent access, tunnel/provisioning success, and actual handset service in compatibility reports.
