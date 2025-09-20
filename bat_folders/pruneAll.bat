@echo off
setlocal

:: --- Configuration ---
:: Set the name of the branch you want to be the sole, final branch.
set "FINAL_BRANCH_NAME=main"
:: Set the commit message for the new, single commit.
set "COMMIT_MESSAGE=Initial commit"

:: --- WARNING ---
echo.
echo  ===================================================================
echo   WARNING: IRREVERSIBLE ACTION
echo.
echo   This script will permanently DESTROY your entire Git history
echo   and delete ALL other branches, both locally and on the remote.
echo   The current state of your files will become the one and only
echo   commit in a new '%FINAL_BRANCH_NAME%' branch.
echo.
echo   Press CTRL+C NOW to cancel.
echo  ===================================================================
echo.
pause

:: --- Script Logic ---

:: 1. Safety Check: Ensure the working directory is clean
echo.
echo [Step 1/5] Checking for uncommitted changes...
for /f %%i in ('git status --porcelain') do (
    echo.
    echo  ERROR: You have uncommitted changes.
    echo  Please commit or stash them before running this script.
    exit /b 1
)
echo  OK. Working directory is clean.

:: 2. Create a new orphan branch with no history
echo.
echo [Step 2/5] Creating a new, clean history...
git checkout --orphan temp_branch > nul

:: 3. Add all files and create the single, initial commit
git add -A
git commit -m "%COMMIT_MESSAGE%"
echo  OK. New initial commit created.

:: 4. Delete all old local branches
echo.
echo [Step 3/5] Deleting all old local branches...
for /f %%b in ('git branch') do (
    if not "%%b"=="temp_branch" (
        if not "%%b"=="* temp_branch" (
            git branch -D %%b
        )
    )
)

:: 5. Rename the temporary branch to the final name
git branch -m %FINAL_BRANCH_NAME%
echo  OK. Old branches deleted and new '%FINAL_BRANCH_NAME%' branch is ready.

:: 6. Force push to the remote, overwriting its history
echo.
echo [Step 4/5] Force pushing to the remote to erase its history...
git push -f origin %FINAL_BRANCH_NAME%
echo  OK. Remote history has been replaced.

:: 7. Prune stale remote-tracking branches
echo.
echo [Step 5/5] Cleaning up local remote-tracking references...
git remote prune origin
echo.
echo  ===================================================================
echo   SUCCESS!
echo.
echo   Your repository history has been wiped. The current state is now
echo   the one and only commit on the '%FINAL_BRANCH_NAME%' branch.
echo   Note: Any old branches on the remote server may still exist
echo   and need to be deleted manually from the GitHub/GitLab interface.
echo  ===================================================================
echo.

endlocal