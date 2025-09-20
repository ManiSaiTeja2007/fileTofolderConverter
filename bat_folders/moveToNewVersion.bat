@echo off
setlocal

:: --- Configuration ---
:: Set this to the name of your primary branch (e.g., "main" or "master").
set "BRANCH=main"

:: --- Script Logic ---

:: 1. Check for required arguments
if "%~1"=="" (
    echo Usage: moveToNewVersion.bat ^<new-version-tag^> "Commit Message"
    echo Example: moveToNewVersion.bat v2.1.0 "feat: Add user profile page"
    exit /b 1
)
if "%~2"=="" (
    echo Usage: moveToNewVersion.bat ^<new-version-tag^> "Commit Message"
    echo Example: moveToNewVersion.bat v2.1.0 "feat: Add user profile page"
    exit /b 1
)

set "NEW_VERSION=%~1"
set "COMMIT_MESSAGE=%~2"

:: 2. Safety Check: Ensure the working directory is clean
echo.
echo Checking working directory...
for /f %%i in ('git status --porcelain') do (
    echo.
    echo Error: You have uncommitted changes. Please commit or stash them first.
    exit /b 1
)
echo Working directory is clean.

:: 3. Fetch latest tags from the remote
echo.
echo Fetching latest tags from remote...
git fetch --tags origin

:: 4. Find the most recent tag.
set "LATEST_TAG="
for /f "tokens=*" %%a in ('git describe --tags --abbrev=0 2^>nul') do set "LATEST_TAG=%%a"

echo.
if not defined LATEST_TAG (
    :: This block handles the very first version when no tags exist yet.
    echo No previous tags found. This will be the first versioned commit.
    
    git checkout --orphan temp-branch
    git add -A
    git commit -m "%COMMIT_MESSAGE%"
    
    git branch -D %BRANCH%
    git branch -m %BRANCH%
) else (
    :: This block handles all subsequent versions.
    echo Found previous version: %LATEST_TAG%
    echo Squashing all commits since %LATEST_TAG% into one...
    
    git reset --soft %LATEST_TAG%
    git commit -m "%COMMIT_MESSAGE%"
)

:: 5. Create a new annotated tag for the release
echo.
echo Tagging new version as %NEW_VERSION%...
git tag -a %NEW_VERSION% -m "%COMMIT_MESSAGE%"

:: 6. Push the rewritten branch and the new tag to the remote
echo.
echo Pushing to remote...
git push --force-with-lease origin %BRANCH%
git push origin %NEW_VERSION%

echo.
echo Successfully created and pushed version %NEW_VERSION%!

endlocal