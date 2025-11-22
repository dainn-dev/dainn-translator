# PowerShell script to create desktop shortcut for Dainn Screen Translator

$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "Dainn Screen Translator.lnk"
$ProjectPath = $PSScriptRoot
$BatFilePath = Join-Path $ProjectPath "run.bat"
$IconPath = Join-Path $ProjectPath "resources\logo.ico"

# Create shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatFilePath
$Shortcut.WorkingDirectory = $ProjectPath
$Shortcut.Description = "Launch Dainn Screen Translator"

# Set icon if available
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}

$Shortcut.Save()

Write-Host "Desktop shortcut created successfully at: $ShortcutPath" -ForegroundColor Green
Write-Host "Shortcut points to: $BatFilePath" -ForegroundColor Cyan

