$ErrorActionPreference = "Stop"

$connectUrl = if ($env:KAFKA_CONNECT_URL) { $env:KAFKA_CONNECT_URL } else { "http://localhost:8083" }
$connectorName = if ($env:DEBEZIUM_CONNECTOR_NAME) { $env:DEBEZIUM_CONNECTOR_NAME } else { "postgres-cdc-connector" }
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$configFile = if ($args.Count -gt 0) { $args[0] } else { Join-Path $scriptDir "..\debezium\postgres-connector-config.json" }

Write-Host "Registering Debezium connector '$connectorName' at $connectUrl"

$configJson = Get-Content -Raw $configFile
Invoke-RestMethod `
    -Method Put `
    -Uri "$connectUrl/connectors/$connectorName/config" `
    -ContentType "application/json" `
    -Body $configJson | ConvertTo-Json -Depth 20

Write-Host "Connector status:"
Invoke-RestMethod `
    -Method Get `
    -Uri "$connectUrl/connectors/$connectorName/status" | ConvertTo-Json -Depth 20
