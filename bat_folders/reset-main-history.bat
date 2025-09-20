@echo off
setlocal

:: --- Configuration ---
set "BRANCH_NAME=main"
set "COMMIT_MESSAGE=Initial commit"

:: --- WARNING ---
echo.
echo  ===================================================================
echo   WARNING: IRREVERSIBLE ACTION
echo.
echo   This script will permanently DESTROY the history of your
echo   '%BRANCH_NAME%' branch, both locally and on the remote.
echo.
echo   Your other branches will NOT be affected.
echo.
echo   Press CTRL+C NOW to cancel.
echo  ===================================================================
echo.
pause

:: --- Script Logic ---

:: 1. Safety Check for uncommitted changes
echo.
echo [Step 1/4] Checking for uncommitted changes...
for /f %%i in ('git status --porcelain') do (
    echo.
    echo  ERROR: You have uncommitted changes.
    echo  Please commit or stash them before running this script.
    exit /b 1
)
echo  OK. Working directory is clean.

:: 2. Create a new orphan branch with no history
echo.
echo [Step 2/4] Creating a new, clean history in a temporary branch...
git checkout --orphan temp_branch > nul

:: 3. Add all files and create the single, initial commit
git add -A
git commit -m "%COMMIT_MESSAGE%"
echo  OK. New initial commit created.

:: 4. Delete the old main branch and rename the new one
echo.
echo [Step 3/4] Replacing old '%BRANCH_NAME%' branch...
git branch -D %BRANCH_NAME%
git branch -m %BRANCH_NAME%
echo  OK. New '%BRANCH_NAME%' branch is ready.

:: 5. Force push to the remote, overwriting its history
echo.
echo [Step 4/4] Force pushing to the remote to erase the branch history...
git push -f origin %BRANCH_NAME%
echo.
echo  ===================================================================
echo   SUCCESS!
echo.
echo   The history for the '%BRANCH_NAME%' branch has been wiped.
echo   The current state is now the one and only commit.
echo  ===================================================================
echo.

endlocal