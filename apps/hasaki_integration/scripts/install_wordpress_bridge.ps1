param(
    [string]$WordPressRoot = 'D:\baitap\htdocs\shopdongho',
    [string]$BackupDirectory = 'C:\Users\Yen Nhi\frappe-crm-backups\wordpress-a48-20261124',
    [string]$PrivateDirectory = 'C:\Users\Yen Nhi\frappe-crm-backups\hasaki-integration-private'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$root = (Resolve-Path -LiteralPath $WordPressRoot).Path
if (-not (Test-Path -LiteralPath (Join-Path $root 'wp-load.php'))) { throw 'Existing WordPress is required' }
if (-not (Test-Path -LiteralPath (Join-Path $BackupDirectory 'wordpress-database.sql'))) { throw 'Complete the existing-site backup first' }
$pluginSource = Join-Path $workspaceRoot 'wordpress-plugin\hasaki-crm-bridge\hasaki-crm-bridge.php'
$pluginDirectory = Join-Path $root 'wp-content\plugins\hasaki-crm-bridge'
$pluginTarget = Join-Path $pluginDirectory 'hasaki-crm-bridge.php'
New-Item -ItemType Directory -Path $PrivateDirectory -Force | Out-Null
$privateFile = Join-Path $PrivateDirectory 'wordpress-secrets.php'

# The command output contains secrets; consume it in memory and never print it.
$setupOutput = docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost execute hasaki_integration.local_setup.configure_existing_wordpress
if ($LASTEXITCODE -ne 0) { throw 'CRM local bridge configuration failed' }
try { $credentials = ($setupOutput -join "`n") | ConvertFrom-Json } catch { throw 'CRM returned an invalid setup response' }
foreach ($value in @($credentials.api_key, $credentials.api_secret, $credentials.webhook_secret)) {
    if ($value -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected credential format' }
}
$privateContents = @"
<?php
// Local credentials, outside the webroot and Git repository.
if (!defined('DB_NAME')) { return; }
define('HASAKI_CRM_BASE_URL', 'http://127.0.0.1:8000');
define('HASAKI_CRM_SITE', 'crm.localhost');
define('HASAKI_CRM_API_KEY', '$($credentials.api_key)');
define('HASAKI_CRM_API_SECRET', '$($credentials.api_secret)');
define('HASAKI_WC_WEBHOOK_SECRET', '$($credentials.webhook_secret)');
"@
[System.IO.File]::WriteAllText($privateFile, $privateContents + "`n", (New-Object System.Text.UTF8Encoding($false)))

$configFile = Join-Path $root 'wp-config.php'
$config = [System.IO.File]::ReadAllText($configFile)
$marker = '// Hasaki CRM Bridge: load local credentials outside the webroot.'
if (-not $config.Contains($marker)) {
    $anchor = "require_once ABSPATH . 'wp-settings.php';"
    if (([regex]::Matches($config, [regex]::Escape($anchor))).Count -ne 1) { throw 'Cannot locate the single WordPress bootstrap anchor; config left unchanged' }
    $privatePhpPath = $privateFile.Replace('\', '/')
    $include = "$marker`nif (is_readable('$privatePhpPath')) { require_once '$privatePhpPath'; }`n`n"
    [System.IO.File]::WriteAllText($configFile, $config.Replace($anchor, $include + $anchor), (New-Object System.Text.UTF8Encoding($false)))
}
New-Item -ItemType Directory -Path $pluginDirectory -Force | Out-Null
if (Test-Path -LiteralPath $pluginTarget) {
    $pluginBackup = Join-Path $BackupDirectory 'hasaki-crm-bridge-before-update.php'
    if (-not (Test-Path -LiteralPath $pluginBackup)) { Copy-Item -LiteralPath $pluginTarget -Destination $pluginBackup }
}
Copy-Item -LiteralPath $pluginSource -Destination $pluginTarget -Force
Write-Output 'Installed Hasaki CRM Bridge source; local credentials saved outside webroot/source.'
Write-Output 'Existing CRM user: tuvan@hasaki.example; no new User or Role created.'
