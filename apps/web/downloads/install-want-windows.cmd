@echo off
setlocal

set "CHROME_PATH="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if not defined CHROME_PATH (
  echo Google Chrome was not found. Install Chrome, then run this installer again.
  pause
  exit /b 1
)

set "EXTENSION_DIR=%LocalAppData%\WANT\extension"
set "ARCHIVE_PATH=%TEMP%\want-chrome-%RANDOM%-%RANDOM%.zip"
set "ARCHIVE_URL=https://snowsadh.github.io/want/downloads/want-chrome.zip"

echo Downloading WANT!
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference = 'Stop'; New-Item -ItemType Directory -Force -Path $env:EXTENSION_DIR | Out-Null; Invoke-WebRequest -Uri $env:ARCHIVE_URL -OutFile $env:ARCHIVE_PATH; Expand-Archive -LiteralPath $env:ARCHIVE_PATH -DestinationPath $env:EXTENSION_DIR -Force"
if errorlevel 1 (
  echo WANT! could not be downloaded. Please try again.
  pause
  exit /b 1
)

if not exist "%EXTENSION_DIR%\manifest.json" (
  echo The downloaded extension is incomplete. Please try again.
  pause
  exit /b 1
)

powershell.exe -NoProfile -Command "Set-Clipboard -Value $env:EXTENSION_DIR"
start "" explorer.exe "%EXTENSION_DIR%"
start "" "%CHROME_PATH%" "chrome://extensions/"
del /q "%ARCHIVE_PATH%" >nul 2>&1

echo.
echo WANT! is downloaded. The extension folder path is on your clipboard.
echo Chrome requires one final approval:
echo   1. Turn on Developer mode.
echo   2. Click Load unpacked.
echo   3. Paste the copied path into the folder chooser address bar.
echo   4. Press Enter and select the extension folder.
echo.
pause
