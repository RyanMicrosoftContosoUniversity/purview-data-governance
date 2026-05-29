<#
.SYNOPSIS
    Deploys the Purview-to-Fabric self-service access workflow infrastructure.

.DESCRIPTION
    Creates the target resource group (if it doesn't exist) and runs an
    Azure Resource Manager deployment using the main.bicep template.

.PARAMETER ResourceGroupName
    Name of the Azure resource group to deploy into.

.PARAMETER Location
    Azure region for the resource group and resources. Defaults to eastus2.

.PARAMETER EnvironmentName
    Deployment environment label (dev, staging, prod). Defaults to dev.
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [string]$Location = "eastus2",

    [ValidateSet("dev", "staging", "prod")]
    [string]$EnvironmentName = "dev"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== Purview-to-Fabric Access Workflow — Infrastructure Deployment ===" -ForegroundColor Cyan
Write-Host "  Resource Group : $ResourceGroupName"
Write-Host "  Location       : $Location"
Write-Host "  Environment    : $EnvironmentName"
Write-Host ""

# Ensure the resource group exists
Write-Host "[1/2] Ensuring resource group '$ResourceGroupName' exists..." -ForegroundColor Yellow
az group create `
    --name $ResourceGroupName `
    --location $Location `
    --tags "project=purview-fabric-access" "environment=$EnvironmentName" `
    --output none

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create or verify resource group."
    exit 1
}

# Deploy the Bicep template
Write-Host "[2/2] Deploying Bicep template..." -ForegroundColor Yellow
$deploymentName = "pvfab-$EnvironmentName-$(Get-Date -Format 'yyyyMMddHHmmss')"

az deployment group create `
    --name $deploymentName `
    --resource-group $ResourceGroupName `
    --template-file "$PSScriptRoot\main.bicep" `
    --parameters "$PSScriptRoot\parameters.json" `
    --parameters environmentName=$EnvironmentName `
    --output table

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed. Check the Azure portal for details."
    exit 1
}

Write-Host ""
Write-Host "Deployment '$deploymentName' completed successfully." -ForegroundColor Green
