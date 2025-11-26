# Microsoft Fabric HIPAA Security & Compliance Implementation Guide

> **Disclaimer:** This material is provided as-is based on best efforts and may not be maintained to stay current with product updates. Please refer to the [DISCLAIMER](DISCLAIMER.md) for full terms.

## Overview
Microsoft Fabric is a unified analytics platform that can support HIPAA-regulated workloads when configured with defense-in-depth controls across Microsoft Fabric, Microsoft Entra ID, Microsoft Purview, Microsoft Defender, and core Azure services. This guide provides a practical checklist and implementation playbook for security architects, compliance officers, and engineering leads to implement, document, and validate HIPAA safeguards for Fabric-based data warehousing, analytics, and data engineering workloads.

### Purpose
- Provide a full HIPAA Security Rule control checklist tailored to Microsoft Fabric.
- Give step-by-step implementation guidance for Fabric and supporting Azure services.
- Supply validation steps and evidence collection guidance so auditors can confirm control effectiveness.

### Assumptions
- A Microsoft Fabric tenant is available under an executed BAA with Microsoft.
- Identity is centralized in Microsoft Entra ID with Conditional Access and MFA available.
- Baseline Azure security services (Key Vault, Private Link, Defender for Cloud, Monitor/Sentinel) are permitted.
- Network egress is controlled via organizational policies (e.g., firewall, secure web gateways).

### Scope
- **In scope:** HIPAA Security Rule administrative, physical, and technical safeguards relevant to Fabric workloads; applicable Privacy/Breach provisions where operationally material (e.g., breach detection/notification readiness, minimum necessary). 
- **Out of scope:** Non-technical Privacy Rule processes (e.g., Notice of Privacy Practices), business process-level policies unrelated to Fabric, and organizational HR processes.

## Architecture & Responsibility Model
- **Microsoft responsibility (under the BAA):** Physical security of datacenters, infrastructure patching of Fabric platform services, default encryption at rest and in transit, service availability SLAs, and core service resiliency.
- **Customer responsibility:** Tenant configuration, identity and access management, network isolation, data classification, DLP, key management (if using CMK), logging, incident response, backup/restore strategies, and validation of controls.
- **Architecture highlights:**
  - Fabric workspaces mapped to data domains with least-privilege workspace roles.
  - OneLake storage with default encryption; optional Customer-Managed Keys (CMK) via Azure Key Vault.
  - Fabric items (lakehouses, warehouses, semantic models, notebooks, pipelines) governed by Purview policies, sensitivity labels, and DLP.
  - Private network paths to data sources using Azure Private Link/Private Endpoints; secured outbound access via managed VNets where applicable.
  - Centralized monitoring with Fabric audit logs + Azure Monitor/Microsoft Sentinel + Defender for Cloud workloads.

## HIPAA Control Mapping for Microsoft Fabric
Use the checklist tables below to track implementation and evidence. Status column options: [ ] Not started, [ ] In progress, [ ] Implemented, [ ] Verified.

### Administrative Safeguards
| HIPAA Control ID | Control Name | Implementation in Microsoft Fabric & Azure | Validation / Evidence Steps | Reference Docs | Status |
|------------------|--------------|---------------------------------------------|------------------------------|----------------|--------|
| 164.308(a)(1) | Security Management Process | Use Microsoft Purview Compliance Manager HIPAA template; conduct risk assessment for Fabric workspaces, dataflows, warehouses; enable Defender for Cloud regulatory compliance dashboard. | Export Compliance Manager HIPAA report; capture Defender for Cloud HIPAA dashboard screenshot; retain risk register with Fabric-specific findings. | [Purview Compliance Manager](https://learn.microsoft.com/en-us/purview/compliance-manager)<br>[Defender for Cloud Regulatory Compliance](https://learn.microsoft.com/en-us/azure/defender-for-cloud/regulatory-compliance-dashboard) | [ ] |
| 164.308(a)(1)(ii)(A) | Risk Analysis | Conduct an accurate and thorough assessment of the potential risks and vulnerabilities to the confidentiality, integrity, and availability of electronic protected health information in Fabric. | Complete risk assessment documentation; vulnerability scan reports; threat modeling for Fabric workspaces; risk register with likelihood and impact ratings. | [Azure Security Benchmark](https://learn.microsoft.com/en-us/azure/security/benchmarks/overview)<br>[Microsoft Cloud Security Benchmark](https://learn.microsoft.com/en-us/security/benchmark/azure/overview) | [ ] |
| 164.308(a)(1)(ii)(B) | Risk Management | Apply remediation plans for identified risks; enforce Conditional Access, MFA, DLP, private endpoints, RBAC; track exceptions with expiry. | Show policy objects (CA, DLP) and change records; review exception list with approvals and dates. | [Conditional Access](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/overview)<br>[Azure Private Link](https://learn.microsoft.com/en-us/azure/private-link/private-link-overview) | [ ] |
| 164.308(a)(1)(ii)(C) | Sanction Policy | Apply appropriate sanctions against workforce members who fail to comply with security policies and procedures of Fabric PHI handling. | HR policy documentation; disciplinary action records (anonymized); training acknowledgments; escalation procedures for security violations. | [Workforce Security Best Practices](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/organize/cloud-security) | [ ] |
| 164.308(a)(1)(ii)(D) | Information System Activity Review | Enable Fabric audit logs; configure log forwarding to Sentinel; set weekly review of access/anomaly reports. | Verify Fabric Admin portal → Tenant settings → Audit logs enabled; check Sentinel workspace for Fabric log tables and weekly review evidence. | [Fabric Audit Logs](https://learn.microsoft.com/en-us/fabric/admin/monitoring-workspace)<br>[Microsoft Sentinel Overview](https://learn.microsoft.com/en-us/azure/sentinel/overview) | [ ] |
| 164.308(a)(2) | Assigned Security Responsibility | Identify the security official who is responsible for the development and implementation of HIPAA security policies and procedures for Fabric workloads. | Document security officer designation; role description; accountability matrix for Fabric security responsibilities; contact information in incident response plans. | [Azure Security Best Practices](https://learn.microsoft.com/en-us/azure/security/fundamentals/best-practices-and-patterns)<br>[Security Organization](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/organize/cloud-security) | [ ] |
| 164.308(a)(3)(i) | Workforce Security | Provision access through Entra security groups; enforce just-in-time (JIT) via PIM for Fabric admin roles; disable leavers promptly. | Review Entra ID access reviews; confirm PIM assignment history for Fabric admin roles; check deprovisioning tickets. | [Entra ID Access Reviews](https://learn.microsoft.com/en-us/azure/active-directory/governance/access-reviews-overview)<br>[PIM for Azure Resources](https://learn.microsoft.com/en-us/azure/active-directory/privileged-identity-management/pim-configure) | [ ] |
| 164.308(a)(3)(ii)(A) | Authorization and/or Supervision | Implement procedures for the authorization and/or supervision of workforce members who work with PHI in Fabric workspaces or locations where it might be accessed. | Supervisor approval records for PHI access; delegation authorities for workspace access; supervision audit trails for high-privilege users. | [Fabric Workspace Management](https://learn.microsoft.com/en-us/fabric/fundamentals/roles-workspaces)<br>[Entra ID Management Units](https://learn.microsoft.com/en-us/azure/active-directory/roles/administrative-units) | [ ] |
| 164.308(a)(3)(ii)(B) | Workforce Clearance | Map PHI access to approved groups; use Fabric item permissions and RLS/CLS to restrict PHI; document approval workflow. | Inspect group membership approvals; verify Fabric dataset RLS roles for PHI tables; attach approval records. | [Fabric Row-Level Security](https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security)<br>[Power BI RLS](https://learn.microsoft.com/en-us/power-bi/enterprise/service-admin-rls)<br>[Fabric OneLake Security](https://learn.microsoft.com/en-us/fabric/onelake/security/get-started-security) | [ ] |
| 164.308(a)(3)(ii)(C) | Termination Procedures | Implement procedures for terminating access to PHI when employment or arrangement with workforce member ends or when access is no longer appropriate. | Offboarding checklist with Fabric access removal; automated deprovisioning workflows; exit interview documentation; account closure verification. | [Entra ID Lifecycle Workflows](https://learn.microsoft.com/en-us/azure/active-directory/governance/what-are-lifecycle-workflows)<br>[Access Review Automation](https://learn.microsoft.com/en-us/azure/active-directory/governance/access-reviews-overview) | [ ] |
| 164.308(a)(4)(i) | Information Access Management | Use workspace roles (Viewer/Contributor/Admin) with least privilege; apply item-level permissions and RLS/CLS; enforce Purview access policies. | Review Fabric workspace permissions; confirm RLS rules in warehouses/Power BI datasets; verify Purview access policies in place. | [Fabric Workspace Roles](https://learn.microsoft.com/en-us/fabric/get-started/roles-workspaces)<br>[Purview Access Policies](https://learn.microsoft.com/en-us/purview/concept-policies-data-owner) | [ ] |
| 164.308(a)(4)(ii)(A) | Isolating Healthcare Clearinghouse Functions | If applicable, isolate clearinghouse operations from other Fabric workloads using separate workspaces, network isolation, and distinct access controls. | Documentation of clearinghouse isolation architecture; network segmentation configuration; separate identity management for clearinghouse functions. | [Fabric Workspace Inbound Access](https://learn.microsoft.com/en-us/fabric/security/security-workspace-enable-inbound-access-protection)<br>[Fabric Workspace Outbound Access](https://learn.microsoft.com/en-us/fabric/security/workspace-outbound-access-protection-set-up?tabs=fabric-portal-1) <br>[Azure Network Security](https://learn.microsoft.com/en-us/azure/security/fundamentals/network-overview) | [ ] |
| 164.308(a)(5)(i) | Security Awareness & Training | Deliver Fabric security training covering PHI handling, DLP, and export controls; phishing and data handling campaigns. | Training completion reports; quiz results; sign-offs. | [Microsoft Security Training](https://learn.microsoft.com/en-us/security/)<br>[Security Awareness Best Practices](https://learn.microsoft.com/en-us/security/zero-trust/deploy/identity) | [ ] |
| 164.308(a)(5)(ii)(A) | Security Reminders | Implement periodic security reminders about PHI protection policies, Fabric usage guidelines, and incident reporting procedures. | Security reminder email logs; poster campaign documentation; newsletter archives; awareness campaign metrics. | [Compliance Training Management](https://learn.microsoft.com/en-us/microsoft-365/compliance/communication-compliance) | [ ] |
| 164.308(a)(5)(ii)(B) | Protection from Malicious Software | Enable Defender for Endpoint on all devices accessing Fabric; implement email security and safe attachments policies for PHI-related communications. | Defender for Endpoint deployment reports; email security policy configuration; malware detection logs; quarantine reports. | [Defender for Endpoint](https://learn.microsoft.com/en-us/microsoft-365/security/defender-endpoint/microsoft-defender-endpoint)<br>[Defender for Office 365](https://learn.microsoft.com/en-us/microsoft-365/security/office-365-security/overview) | [ ] |
| 164.308(a)(6)(i) | Security Incident Procedures | Integrate Fabric logs with Sentinel; create playbooks for PHI access anomalies, exfiltration, and breach notification steps. | Validate Sentinel analytics rules targeting Fabric logs; show incident runbooks and post-incident reviews. | [Azure Sentinel Playbooks](https://learn.microsoft.com/en-us/azure/sentinel/automate-incident-handling-with-automation-rules)<br>[Fabric Security Incident Response](https://learn.microsoft.com/en-us/fabric/security/security-fundamentals) | [ ] |
| 164.308(a)(6)(ii) | Response and Reporting | Establish procedures to identify, respond to, report, and mitigate security incidents affecting PHI in Fabric environments. | Incident response plan documentation; incident reporting templates; escalation procedures; regulatory notification workflows; post-incident analysis reports. | [Breach Notification Requirements](https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech) | [ ] |
| 164.308(a)(7)(i) | Contingency Plan | Define BCDR for Fabric: OneLake geo-redundancy, backup exports, cross-region data copy, runbook for workspace recovery. | Evidence of backup schedules; test restoration of lakehouse/warehouse exports; DR exercise report. | [OneLake Disaster Recovery](https://learn.microsoft.com/en-us/fabric/onelake/onelake-disaster-recovery)<br>[Azure Backup Guidance](https://learn.microsoft.com/en-us/azure/backup/guidance-best-practices) | [ ] |
| 164.308(a)(8) | Evaluation | Annual HIPAA evaluation of Fabric configuration using this checklist plus Compliance Manager assessments. | Completed annual assessment record; tracked remediation actions. | [Compliance Manager Assessments](https://learn.microsoft.com/en-us/purview/compliance-manager-assessments)<br>[Security Posture Management](https://learn.microsoft.com/en-us/azure/defender-for-cloud/secure-score-security-controls) | [ ] |
| 164.308(b)(1) | Business Associate Contracts | Ensure BAA with Microsoft is executed; BAA with downstream processors (e.g., SIEM, backup providers). | Copy of BAA; vendor contract list with HIPAA clauses. | [Microsoft HIPAA BAA](https://aka.ms/baa)<br>[Azure Compliance Documentation](https://learn.microsoft.com/en-us/azure/compliance/) | [ ] |

### Physical Safeguards (customer responsibilities in Fabric context)
| HIPAA Control ID | Control Name | Implementation in Microsoft Fabric & Azure | Validation / Evidence Steps | Reference Docs | Status |
|------------------|--------------|--------------------------------------------|------------------------------|----------------| -------|
| 164.310(a)(1) | Facility Access Controls | Rely on Microsoft datacenter controls under BAA; restrict Fabric access to trusted networks with Conditional Access/location policies. | Review BAA/SOC reports; verify CA policy limiting access locations; document reliance on Microsoft physical controls. | [Azure Physical Security](https://learn.microsoft.com/en-us/azure/security/fundamentals/physical-security)<br>[Conditional Access Location Policies](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/location-condition) | [ ] |
| 164.310(a)(2)(i) | Contingency Operations | Establish procedures that allow facility access in support of data restoration under disaster recovery and emergency mode operations plans. | Documented emergency facility access procedures; emergency contact lists; key holder designations; facility access logs during emergencies. | [Business Continuity Planning](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/enterprise-scale/business-continuity-and-disaster-recovery)<br>[Emergency Access Procedures](https://learn.microsoft.com/en-us/azure/active-directory/roles/security-emergency-access) | [ ] |
| 164.310(a)(2)(ii) | Facility Security Plan | Implement policies and procedures to safeguard facilities and equipment from unauthorized physical access, tampering, and theft. | Facility security plan documentation; physical security assessment reports; access control system configurations; surveillance system documentation. | [Physical Security Best Practices](https://learn.microsoft.com/en-us/azure/security/fundamentals/physical-security)<br>[Facility Security Planning](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/secure/security-top-10#9-secure-physical-access) | [ ] |
| 164.310(a)(2)(iii) | Access Control and Validation | Implement procedures to control and validate person's access to facilities based on role/function, including visitor control and software access control. | Visitor access logs; badge access records; role-based facility access matrix; software access control procedures; visitor escort policies. | [Physical Access Controls](https://learn.microsoft.com/en-us/azure/security/fundamentals/physical-security)<br>[Conditional Access Device Policies](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/concept-conditional-access-conditions) | [ ] |
| 164.310(a)(2)(iv) | Maintenance Records | Document repairs and modifications to physical facility components related to security (hardware, walls, doors, locks). | Facility maintenance logs; security system modification records; lock change documentation; hardware replacement logs; security incident repair records. | [Asset Management](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/secure/security-top-10#7-enable-cloud-security-posture-management)<br>[Change Management](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/manage/considerations/operational-compliance) | [ ] |
| 164.310(b) | Workstation Use | Specify proper functions to be performed and physical attributes of workstation surroundings that can access PHI through Fabric. | Workstation usage policies; approved workstation configurations; environmental controls documentation; workstation location restrictions for PHI access. | [Secure Workstation Configuration](https://learn.microsoft.com/en-us/azure/security/fundamentals/operational-security#secure-workstation-configuration)<br>[Privileged Access Workstations](https://learn.microsoft.com/en-us/security/compass/privileged-access-devices) | [ ] |
| 164.310(c) | Workstation Security | Enforce Intune device compliance and Conditional Access requiring managed devices for Fabric; block downloads of PHI where possible. | CA policy screenshot requiring compliant devices; Intune policy reports; DLP/label policy preventing export; physical workstation security measures. | [Intune Device Compliance](https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started)<br>[Conditional Access Device Controls](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/concept-conditional-access-conditions) | [ ] |
| 164.310(d)(1) | Device and Media Controls | Govern receipt and removal of hardware and electronic media containing PHI into and out of facilities. | Device movement logs; media tracking records; checkout/checkin procedures; approved device inventory; transport security measures. | [Device Management](https://learn.microsoft.com/en-us/mem/intune/fundamentals/what-is-intune)<br>[Mobile Device Management](https://learn.microsoft.com/en-us/mem/intune/enrollment/device-enrollment) | [ ] |
| 164.310(d)(2)(i) | Disposal | Address final disposition of PHI and/or hardware or electronic media on which it is stored. | Media disposal logs; certificate of destruction; secure wipe verification; disposal vendor agreements; sanitization procedures documentation. | [Secure Data Disposal](https://learn.microsoft.com/en-us/azure/security/fundamentals/data-encryption-best-practices#secure-data-disposal)<br>[Azure Information Protection](https://learn.microsoft.com/en-us/azure/information-protection/what-is-information-protection) | [ ] |
| 164.310(d)(2)(ii) | Media Re-use | Remove PHI from electronic media before media are made available for re-use. | Media sanitization logs; data wipe verification procedures; reuse authorization processes; secure erasure tool validation; media lifecycle management. | [Data Sanitization](https://learn.microsoft.com/en-us/azure/security/fundamentals/data-encryption-best-practices#data-sanitization)<br>[BitLocker Data Recovery](https://learn.microsoft.com/en-us/windows/security/operating-system-security/data-protection/bitlocker/bitlocker-recovery-guide-plan) | [ ] |
| 164.310(d)(2)(iii) | Accountability | Maintain record of movements of hardware and electronic media and any person responsible therefore. | Hardware movement tracking logs; media custody chain documentation; responsibility assignment records; device checkout logs; transport authorization records. | [Device Inventory Management](https://learn.microsoft.com/en-us/mem/intune/remote-actions/device-inventory) | [ ] |
| 164.310(d)(2)(iv) | Data Backup and Storage | Create retrievable, exact copy of PHI when needed, before movement of equipment. | Backup verification logs; data integrity check reports; backup storage location documentation; restoration test results; backup encryption validation. | [Azure Backup](https://learn.microsoft.com/en-us/azure/backup/backup-overview)<br>[OneLake Backup Strategy](https://learn.microsoft.com/en-us/fabric/onelake/onelake-disaster-recovery) | [ ] |

### Technical Safeguards
| HIPAA Control ID | Control Name | Implementation in Microsoft Fabric & Azure | Validation / Evidence Steps | Reference Docs | Status |
|------------------|--------------|--------------------------------------------|------------------------------|----------------| --------|
| 164.312(a)(1) | Access Control (general) | Enforce least privilege via Fabric workspace roles and item permissions; use Purview access policies; block public sharing; require MFA. | Fabric Admin portal: verify tenant setting "Enable service principals" as needed; review workspace permissions and sharing settings; confirm MFA/Conditional Access in Entra. | [Fabric Security Fundamentals](https://learn.microsoft.com/en-us/fabric/security/security-fundamentals)<br>[Fabric Workspace Security](https://learn.microsoft.com/en-us/fabric/get-started/roles-workspaces) | [ ] |
| 164.312(a)(2)(i) | Unique User Identification | All users authenticate via Entra ID; disable shared accounts; use service principals/managed identities for automation with logging. | Review Entra sign-in logs for user principal names; confirm no shared accounts; check service principal assignments. | [Entra ID Identity Management](https://learn.microsoft.com/en-us/azure/active-directory/fundamentals/active-directory-whatis)<br>[Managed Identities](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview) | [ ] |
| 164.312(a)(2)(ii) | Emergency Access Procedure | Create break-glass accounts with monitored Conditional Access exclusion; document emergency process for Fabric admin access. | Verify break-glass accounts with strong auth and exclusion records; periodic access review evidence. | [Emergency Access Accounts](https://learn.microsoft.com/en-us/azure/active-directory/roles/security-emergency-access)<br>[Break-Glass Account Management](https://learn.microsoft.com/en-us/azure/active-directory/fundamentals/security-operations-privileged-accounts) | [ ] |
| 164.312(a)(2)(iii) | Automatic Logoff | Set session timeouts through Entra/Conditional Access sign-in frequency; configure idle timeouts in Power BI/Fabric as applicable. | Conditional Access policy export; user experience validation of session timeout; screenshots of applied settings. | [Conditional Access Session Controls](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/concept-conditional-access-session)<br>[Sign-in Frequency Controls](https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/howto-conditional-access-session-lifetime) | [ ] |
| 164.312(a)(2)(iv) | Encryption & Decryption | Fabric encrypts at rest by default; configure CMK for Fabric (Azure Key Vault, key rotation policies); enforce encryption on data sources/targets. | Admin portal: confirm CMK/Double Encryption if used; Key Vault key rotation logs; verify source connectors use encrypted endpoints. | [Fabric Customer-Managed Keys](https://learn.microsoft.com/en-us/fabric/security/security-fundamentals#customer-managed-keys)<br>[Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview) | [ ] |
| 164.312(b) | Audit Controls | Enable Fabric audit logs; warehouse/lakehouse SQL auditing; send to Sentinel/Monitor; alert on anomalous access/export. | Check Admin portal → Audit logs enabled; verify logs landing in Log Analytics/Sentinel; show analytics rules and sample queries. | [Fabric Audit Logs](https://learn.microsoft.com/en-us/fabric/admin/monitoring-workspace)<br>[Azure Monitor Logs](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-platform-logs) | [ ] |
| 164.312(c)(1) | Integrity | Use Purview sensitivity labels, data quality rules, and lineage; enable change data capture/versioning where applicable; restrict direct write access. | Purview lineage view for PHI datasets; Fabric permissions showing restricted write roles; audit trails for schema changes. | [Purview Data Lineage](https://learn.microsoft.com/en-us/purview/concept-data-lineage)<br>[Fabric Information Protection](https://learn.microsoft.com/en-us/fabric/governance/information-protection) | [ ] |
| 164.312(c)(2) | Mechanism to Authenticate Electronic Protected Health Information | Implement electronic mechanisms to corroborate that PHI has not been altered or destroyed in an unauthorized manner. | Digital signature validation; checksum verification logs; data integrity monitoring alerts; version control audit trails; hash verification for data transfers. | [Azure Information Protection](https://learn.microsoft.com/en-us/azure/information-protection/what-is-information-protection) | [ ] |
| 164.312(d) | Person or Entity Authentication | Require MFA and compliant devices; use phishing-resistant methods (FIDO2/Windows Hello); enforce certificate-based auth for service principals when possible. | Conditional Access policy requiring MFA; Auth method usage report; service principal credential policy review. | [Azure MFA](https://learn.microsoft.com/en-us/azure/active-directory/authentication/concept-mfa-howitworks)<br>[Passwordless Authentication](https://learn.microsoft.com/en-us/azure/active-directory/authentication/concept-authentication-passwordless) | [ ] |
| 164.312(e)(1) | Transmission Security | TLS 1.2+ enforced; use Private Link for data sources; restrict public network data movement; enable HTTPS-only endpoints; configure managed VNet for pipelines. | Verify connectors use private endpoints; check network isolation settings for Data Pipelines; inspect TLS settings on ingress/egress resources. | [Fabric Private Endpoints](https://learn.microsoft.com/en-us/fabric/security/security-fundamentals#private-endpoints)<br>[Azure Private Link](https://learn.microsoft.com/en-us/azure/private-link/private-link-overview) | [ ] |
| 164.312(e)(2)(i) | Integrity Controls (in transit) | Use message-level integrity via HTTPS and signed APIs; validate checksums when moving data via pipelines; use Dataflows Gen2 with secured endpoints. | Pipeline activity logs showing checksum/row counts; review connector settings; Sentinel rules on tampering anomalies. | [Data Pipeline Security](https://learn.microsoft.com/en-us/fabric/data-engineering/data-engineering-overview)<br>[Dataflows Gen2](https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-overview) | [ ] |
| 164.312(e)(2)(ii) | Encryption (in transit) | Enforce TLS for all connections; require VPN/ExpressRoute/private endpoints for hybrid sources; disable HTTP endpoints. | Connection configuration screenshots; network firewall rules; test TLS via connection diagnostics. | [TLS Best Practices](https://learn.microsoft.com/en-us/azure/security/fundamentals/tls-certificate-changes)<br>[ExpressRoute Overview](https://learn.microsoft.com/en-us/azure/expressroute/expressroute-introduction) | [ ] |

### Organizational & Additional Considerations
| HIPAA Control ID | Control Name | Implementation in Microsoft Fabric & Azure | Validation / Evidence Steps | Reference Docs | Status |
|------------------|--------------|--------------------------------------------|------------------------------|----------------| -------|
| 164.308(a)(4)(ii)(B) | Access Authorization | Use approval workflows for PHI access; enforce Purview policy approvals; maintain access request tickets. | Access request records; Purview policy change logs; Fabric permission history. | [Purview Access Policies](https://learn.microsoft.com/en-us/purview/legacy/concept-policies-data-owner)<br>[Entra ID Entitlement Management](https://learn.microsoft.com/en-us/azure/active-directory/governance/entitlement-management-overview) | [ ] |
| 164.308(a)(4)(ii)(C) | Access Establishment & Modification | Standardize access via Entra groups; apply PIM for admin roles; periodic access reviews. | Group change audit logs; PIM activation history; quarterly access review results. | [Entra ID Group Management](https://learn.microsoft.com/en-us/azure/active-directory/fundamentals/how-to-manage-groups)<br>[PIM Access Reviews](https://learn.microsoft.com/en-us/azure/active-directory/privileged-identity-management/pim-create-azure-ad-roles-and-resource-roles-review) | [ ] |
| 164.308(a)(5)(ii)(C) | Log-in Monitoring | Enable sign-in risk policies; monitor Fabric admin sign-ins; alert on anomalous logins via Defender for Cloud Apps. | Sign-in risk policy configuration; Sentinel analytics for abnormal Fabric logins. | [Entra ID Sign-in Risk](https://learn.microsoft.com/en-us/azure/active-directory/identity-protection/concept-identity-protection-risks)<br>[Defender for Cloud Apps for Power BI](https://learn.microsoft.com/en-us/fabric/governance/service-security-using-defender-for-cloud-apps-controls) | [ ] |
| 164.308(a)(5)(ii)(D) | Password Management | Enforce strong auth via MFA/passwordless; conditional access disallowing legacy auth; restrict service principal secrets. | Entra authentication methods policy; legacy auth blocked report; Key Vault secret expiration policy. | [Passwordless Authentication](https://learn.microsoft.com/en-us/azure/active-directory/authentication/concept-authentication-passwordless)<br>[Authentication Methods Policy](https://learn.microsoft.com/en-us/azure/active-directory/authentication/concept-authentication-methods-manage) | [ ] |
| 164.308(a)(7)(ii)(B) | Disaster Recovery | Define RPO/RTO for Fabric workloads; automate exports of lakehouses/warehouses to secondary region; test restores. | DR test report; automation runbooks; evidence of successful restore rehearsal. | [Azure Site Recovery](https://learn.microsoft.com/en-us/azure/site-recovery/site-recovery-overview)<br>[OneLake Disaster Recovery](https://learn.microsoft.com/en-us/fabric/onelake/onelake-disaster-recovery) | [ ] |
| 164.308(a)(7)(ii)(C) | Emergency Mode Operation Plan | Pre-stage minimum analytics capabilities (e.g., read-only PHI dashboards) in alternate region; ensure break-glass access works. | Documented emergency procedures; screenshots of alternate region workspace; test results. | [Business Continuity Planning](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/enterprise-scale/business-continuity-and-disaster-recovery)<br>[Multi-region Architecture](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/) | [ ] |
| 164.308(a)(7)(ii)(D) | Testing & Revision Procedures | Quarterly tabletop + annual technical DR test for Fabric workloads. | Test schedule and after-action reports; remediation tracking. | [Disaster Recovery Testing](https://learn.microsoft.com/en-us/azure/site-recovery/site-recovery-test-failover-to-azure)<br>[Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/architecture/framework/) | [ ] |
| 164.308(a)(7)(ii)(E) | Applications & Data Criticality | Classify Fabric items by PHI criticality; prioritize backup and monitoring accordingly. | Classification register; mapping of Fabric items to backup/monitoring tiers. | [Data Classification](https://learn.microsoft.com/en-us/purview/create-sensitivity-label)<br>[Azure Backup](https://learn.microsoft.com/en-us/azure/backup/backup-overview) | [ ] |
| 164.316(b)(1) | Documentation | Maintain this checklist, runbooks, and architecture diagrams in a controlled repository with version history. | Repo change history; sign-off records; periodic document review logs. | [Azure DevOps](https://learn.microsoft.com/en-us/azure/devops/)<br>[Documentation Best Practices](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/considerations/naming-and-tagging) | [ ] |

## Detailed Implementation Guides
### Identity & Access Management (164.312(a), 164.308(a)(4))
**Intent:** Ensure only authorized, uniquely identified users/services can access PHI in Fabric.

**Steps:**
1. **Tenant controls:** Fabric Admin portal → Tenant settings → restrict export/sharing (disable Publish to web, restrict external sharing), enable service principal access only for approved scenarios.
2. **Workspace RBAC:** Create dedicated workspaces per data domain; assign Viewer/Contributor/Member/Admin roles via Entra groups; avoid direct user assignments.
3. **Item-level security:**
   - Warehouses/lakehouses: enforce SQL permissions; apply row-level security (RLS) and column-level security (CLS) for PHI tables.
   - Semantic models: define RLS roles; map users/groups accordingly.
4. **Conditional Access & MFA:** Require MFA, compliant device, and location-based controls for all Fabric apps; block legacy authentication.
5. **Privileged access:** Use Entra Privileged Identity Management (PIM) for Fabric admin roles; enforce JIT elevation with approval and auditing.
6. **Service principals/managed identities:** Use managed identities for pipelines/dataflows; store secrets in Key Vault; apply least privilege to data sources.
7. **Break-glass:** Maintain at least two emergency accounts with strong auth, monitored sign-ins, and exclusion only from essential CA policies.

**Evidence collection:** Screenshots of tenant settings; PIM activation logs; RLS definitions; Conditional Access policy exports; Key Vault access policy logs.

### Encryption & Key Management (164.312(a)(2)(iv), 164.312(e))
**Intent:** Protect PHI confidentiality and integrity at rest and in transit.

**Steps:**
1. **At rest:** Fabric encrypts OneLake by default. For CMK, configure Fabric managed key via Azure Key Vault (supporting double encryption if required by policy).
2. **In transit:** Ensure all connectors use HTTPS/TLS 1.2+; disable non-TLS endpoints; prefer Private Link/ExpressRoute for hybrid data sources.
3. **Key management:** Implement Key Vault with RBAC; enable soft delete and purge protection; rotate keys at least annually; monitor key usage/expiration.
4. **Secrets management:** Store credentials in Key Vault; reference them from pipelines/notebooks via managed identities; avoid embedding secrets in code.

**Evidence collection:** Key Vault configuration export (soft delete/purge protection enabled); CMK status in Fabric admin portal; TLS test results; key rotation logs.

### Auditing, Monitoring & Incident Response (164.312(b), 164.308(a)(6))
**Intent:** Record, detect, and respond to unauthorized access or disclosure of PHI.

**Steps:**
1. **Audit logs:** Enable Fabric audit logs (Admin portal → Audit logs); configure diagnostic settings to send to Log Analytics/Sentinel.
2. **SQL auditing:** Enable SQL auditing for warehouses/lakehouses; capture query, data access, and export events.
3. **Analytics rules:** In Sentinel, create rules for anomalous downloads, sharing, admin changes, failed logins, and off-hours access.
4. **Defender integration:** Enable Defender for Cloud Apps (MDA) for Fabric to detect risky sessions and enforce session controls; enable Defender for SQL/Storage where applicable.
5. **Incident workflows:** Define playbooks for PHI exfiltration, anomalous access, and ransomware indicators; integrate notification paths for privacy office/legal.
6. **Retention:** Set log retention aligned to HIPAA record-keeping policies; ensure immutability via workspace retention locks where required.

**Evidence collection:** Sentinel analytics rule list; sample incident with investigation notes; audit log sample; retention policy settings.

### Data Classification, DLP, and Minimum Necessary (164.308(a)(3), 164.308(a)(4), 164.312(c))
**Intent:** Restrict PHI to the minimum necessary and label it for consistent handling.

**Steps:**
1. **Sensitivity labels:** Publish Purview Information Protection labels for PHI/Confidential data; require labels on Fabric items (datasets, reports) and enforce encryption/usage rights where supported.
2. **DLP policies:** Configure Purview/Microsoft 365 DLP policies targeting Fabric (OneLake, Power BI/Fabric) to block or warn on PHI exfiltration (downloads, external sharing, copying to unmanaged devices).
3. **Data discovery:** Use Purview scanning to classify data sources connected to Fabric; enable auto-labeling for PHI patterns.
4. **Access scoping:** Implement RLS/CLS to enforce minimum necessary; restrict export/print/Analyze in Excel for PHI datasets.

**Evidence collection:** DLP policy exports; Purview scan/classification reports; label policy publication status; RLS configurations and test queries.

### Network Protection (164.312(e))
**Intent:** Prevent unauthorized interception of PHI in transit and limit ingress/egress paths.

**Steps:**
1. **Private connectivity:** Use Private Link for data sources (SQL, Storage, Synapse) accessed by Fabric; avoid public endpoints when possible.
2. **Managed VNet for pipelines:** Enable managed virtual networks for Fabric Data Pipelines and Dataflow Gen2; configure private endpoints within managed VNet.
3. **Egress control:** Use firewall rules and NSGs on source/target services; restrict outbound to approved endpoints; consider Azure Firewall/SWG for egress inspection.
4. **DNS:** Ensure private DNS zones resolve private endpoints correctly; block public resolution where not needed.

**Evidence collection:** Private endpoint list with DNS records; pipeline managed VNet settings; firewall rule screenshots; connectivity test logs.

### Backup, Recovery, and Availability (164.308(a)(7))
**Intent:** Ensure PHI availability and recoverability.

**Steps:**
1. **Backups/exports:** Schedule exports of lakehouse/warehouse data to secure Storage Accounts with versioning and immutability (Blob versioning, legal hold if required).
2. **Geo-resilience:** Leverage OneLake geo-redundancy; consider multi-geo workspaces for critical PHI analytics.
3. **Runbooks:** Maintain recovery runbooks for restoring from backups, rehydrating semantic models, and reapplying security settings.
4. **Testing:** Perform annual restore tests; document RPO/RTO results versus objectives.

**Evidence collection:** Backup job definitions; storage immutability settings; DR test reports; runbook repository links.

### Third-Party Management & Integrations (164.308(b))
**Intent:** Ensure downstream services processing PHI meet HIPAA obligations.

**Steps:**
1. **BAA coverage:** Ensure Microsoft BAA is in place; confirm BAAs with SIEM, ticketing, backup, or analytics partners that receive Fabric logs or PHI exports.
2. **Data flow inventory:** Maintain a data flow diagram noting all services touching PHI from Fabric (e.g., Sentinel, external ML endpoints).
3. **Access controls:** Apply least privilege and DLP controls to integrations (API permissions, service principals with minimal scopes).
4. **Termination:** Remove downstream connectors/keys when contracts end; rotate secrets and disable service principals.

**Evidence collection:** BAA copies; vendor list with PHI handling notes; access review records for service principals; change records for connector removal.

### Privacy & Breach Readiness (select provisions relevant to Fabric)
**Intent:** Support minimum necessary and breach detection/notification readiness within Fabric operations.

**Steps:**
1. **Minimum necessary enforcement:** Use RLS/CLS and DLP to restrict PHI exposure; provide de-identified/synthetic datasets for dev/test.
2. **Breach detection:** Configure Sentinel/Defender alerts for mass exports, abnormal sharing, or DLP violations; maintain on-call rotation for investigation.
3. **Breach response:** Document playbook aligned to HIPAA breach notification timelines; include Fabric log sources and evidence preservation steps.

**Evidence collection:** De-identification procedure; alert runbooks; incident drill reports; DLP violation logs with remediation actions.

## Testing, Monitoring, and Continuous Compliance
- **Dashboards:** Build Sentinel workbooks showing Fabric access anomalies, DLP violations, admin changes, and export volumes.
- **Alerts:** Configure alerts for high-risk sign-ins, mass data exports, sharing with external users, PIM activations, and audit log pipeline failures.
- **Metrics:** Track time to remediate incidents, DLP violation counts, % of workspaces with RLS/CLS applied, key rotation age, backup success rate.
- **Cadence:** Weekly log review, monthly access review for PHI datasets, quarterly DLP effectiveness review, annual DR tests and HIPAA evaluation.
- **Automation:** Use Azure Policy/Defender for Cloud to flag non-compliant resources (public endpoints, missing encryption, missing logs). Automate evidence collection via scripts exporting Fabric tenant settings and Sentinel rule configurations.

## References
- Cornell Law: https://www.law.cornell.edu/cfr/text/45/164.310
- HIPAA Security Rule text: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C
- HIPPA Security Rule text 2: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-C/section-164.312
- Microsoft Fabric security fundamentals: https://learn.microsoft.com/en-us/fabric/security/security-fundamentals
- Fabric audit logging: https://learn.microsoft.com/en-us/fabric/admin/monitoring-workspace
- Fabric information protection: https://learn.microsoft.com/en-us/fabric/governance/information-protection
- Fabric data protection (RLS/CLS): https://learn.microsoft.com/en-us/fabric/security/service-admin-row-level-security
- Fabric managed private endpoints: https://learn.microsoft.com/en-us/fabric/security/security-managed-private-endpoints-overview
- Fabric customer-managed keys: https://learn.microsoft.com/en-us/fabric/security/security-fundamentals#customer-managed-keys
- Microsoft Purview access policies: https://learn.microsoft.com/en-us/purview/concept-policies-data-owner
- Microsoft Purview data loss prevention for Fabric/Power BI: https://learn.microsoft.com/en-us/fabric/governance/information-protection
- Azure Key Vault soft delete and purge protection: https://learn.microsoft.com/en-us/azure/key-vault/general/soft-delete-overview
- Conditional Access and MFA: https://learn.microsoft.com/en-us/azure/active-directory/conditional-access/overview
- Microsoft Defender for Cloud Apps for Fabric: https://learn.microsoft.com/en-us/fabric/governance/service-security-using-defender-for-cloud-apps-controls
- Microsoft Sentinel overview: https://learn.microsoft.com/en-us/azure/sentinel/overview
- OneLake and data protection: https://learn.microsoft.com/en-us/fabric/onelake/onelake-overview
- Backup and disaster recovery concepts for Fabric: https://learn.microsoft.com/en-us/azure/reliability/reliability-fabric

