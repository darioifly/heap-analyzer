# === CONFIGURA QUI ===
$PromptDir  = "C:\Users\iflys\projects\Heap Analyzer\prompt-da-eseguire"
$WorkingDir = "C:\Users\iflys\projects\Heap Analyzer"
$QueueDir   = "$env:USERPROFILE\.claude-queue\queue"
# =====================

# Crea la cartella della coda se non esiste
New-Item -ItemType Directory -Force -Path $QueueDir | Out-Null

# Il working_directory nel frontmatter YAML deve avere backslash "escapati" o usare slash normali.
# Uso le slash normali che YAML accetta senza problemi.
$WorkingDirYaml = $WorkingDir -replace '\\', '/'

$priority = 1
Get-ChildItem -Path $PromptDir -Filter *.md | Sort-Object Name | ForEach-Object {
    $src  = $_.FullName
    $dest = Join-Path $QueueDir $_.Name

    $frontmatter = @"
---
priority: $priority
working_directory: $WorkingDirYaml
context_files: []
max_retries: 3
---

"@

    $content = Get-Content -Path $src -Raw -Encoding UTF8
    Set-Content -Path $dest -Value ($frontmatter + $content) -Encoding UTF8

    Write-Host "OK  $($_.Name)  -> priority $priority"
    $priority++
}

Write-Host ""
Write-Host "Fatto. $($priority - 1) prompt in coda in: $QueueDir"