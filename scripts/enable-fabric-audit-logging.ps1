Install-Module -Name ExchangeOnlineManagement -Force
Import-Module ExchangeOnlineManagement

# Connect to Exchange Online (replace with your admin UPN)
Connect-ExchangeOnline -UserPrincipalName "admin@MngEnvMCAP372892.onmicrosoft.com"

Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $true

# Disconnect when done
Disconnect-ExchangeOnline -Confirm:$false

