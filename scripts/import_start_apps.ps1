# Adds every Start-menu app to data\apps.json so Vaani can open it by name (spoken name = Start-menu name).
#   Preview only:  powershell -ExecutionPolicy Bypass -File scripts\import_start_apps.ps1 -DryRun
#   Write it:      powershell -ExecutionPolicy Bypass -File scripts\import_start_apps.ps1
# Your existing entries are kept (they win over generated ones) and a backup is saved as apps.json.bak.
param([switch]$DryRun)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$file = Join-Path $root "data\apps.json"
$map  = [ordered]@{}

if (Test-Path $file) {
    try   { $old = Get-Content $file -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw "data\apps.json is not valid JSON, so nothing was changed. Fix it first. ($_)" }
    if ($old) { foreach ($p in $old.PSObject.Properties) { $map[$p.Name] = [string]$p.Value } }
}
$before = $map.Count

# Never voice-launchable: they change system state, install/remove software, or give remote access.
$risky = 'uninstall|installer|setup|repair|remove|reset|restore|backup|start database|stop database|reload configuration|recovery drive|memory diagnostic|system configuration|registry editor|disk cleanup|defragment|quick assist|ultraviewer|remote desktop|stack builder'
# Left out to keep voice matching precise: shortcuts that only open documentation or web pages.
$noise = 'documentation|manuals|module docs|release notes|faqs|user guide|website|forum|installation notes|additional tools'
$safe  = '^[\w\-. :\\/(){}!]+$'                         # the same characters Vaani allows
$added   = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]

foreach ($a in (Get-StartApps | Sort-Object Name)) {
    $name = ($a.Name -replace '\s+', ' ').Trim().ToLower()
    if (-not $name) { continue }
    if ($map.Contains($name)) { continue }
    if ($name -match $risky) { $skipped.Add("$($a.Name)  - changes system state, installs/removes software, or gives remote access"); continue }
    if ($name -match $noise) { $skipped.Add("$($a.Name)  - documentation/website shortcut"); continue }
    if ($a.AppID -notmatch $safe) { $skipped.Add("$($a.Name)  - its launch address contains a character Vaani blocks"); continue }
    $map[$name] = "shell:AppsFolder\" + $a.AppID
    $added.Add($name)
}

if (-not $DryRun) {
    if (Test-Path $file) { Copy-Item $file "$file.bak" -Force }
    $json = ConvertTo-Json -InputObject $map
    [System.IO.File]::WriteAllText($file, $json, (New-Object System.Text.UTF8Encoding($false)))
}

""
if ($DryRun) { "DRY RUN - nothing was written." }
"Kept $before existing entries, added $($added.Count) new ones, skipped $($skipped.Count)."
""
"You can now say 'open <name>' for:"
($added -join ", ")
if ($skipped.Count) { ""; "Skipped:"; $skipped | ForEach-Object { "  $_" } }
""
"Checking the ones you asked about:"
foreach ($n in 'camera', 'sticky notes', 'whatsapp', 'copilot', 'claude', 'docker desktop') {
    if ($map.Contains($n)) { "  OK       $n" } else { "  MISSING  $n  (not in the Start menu list; see the note about names)" }
}
