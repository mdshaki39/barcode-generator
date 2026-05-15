@echo off
title DocVerify - CA DL AAMVA Tool
color 0B
echo.
echo  ========================================
echo   DocVerify - CA DL AAMVA Tool
echo   Starting server...
echo  ========================================
echo.

set PYTHON=
for %%p in (python python3 py) do (
    %%p --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON=%%p
        goto :found_python
    )
)
echo  [ERROR] Python not found!
echo  https://python.org theke install korun
echo  Install korar somoy "Add Python to PATH" tick korben
echo.
pause
exit /b 1

:found_python
echo  Python found: %PYTHON%
echo  Checking dependencies...

%PYTHON% -m pip show flask >nul 2>&1
if errorlevel 1 (echo  Installing Flask... & %PYTHON% -m pip install flask --quiet --no-warn-script-location)

%PYTHON% -m pip show pdf417gen >nul 2>&1
if errorlevel 1 (echo  Installing pdf417gen... & %PYTHON% -m pip install pdf417gen --quiet --no-warn-script-location)

%PYTHON% -m pip show pillow >nul 2>&1
if errorlevel 1 (echo  Installing Pillow... & %PYTHON% -m pip install pillow --quiet --no-warn-script-location)

%PYTHON% -m pip show python-barcode >nul 2>&1
if errorlevel 1 (echo  Installing python-barcode... & %PYTHON% -m pip install "python-barcode[images]" --quiet --no-warn-script-location)

%PYTHON% -m pip show opencv-python-headless >nul 2>&1
if errorlevel 1 (echo  Installing OpenCV... & %PYTHON% -m pip install opencv-python-headless --quiet --no-warn-script-location)

%PYTHON% -m pip show numpy >nul 2>&1
if errorlevel 1 (echo  Installing NumPy... & %PYTHON% -m pip install numpy --quiet --no-warn-script-location)

%PYTHON% -m pip show svgwrite >nul 2>&1
if errorlevel 1 (echo  Installing svgwrite... & %PYTHON% -m pip install svgwrite --quiet --no-warn-script-location)

echo.
echo  All dependencies ready.
echo  Server starting at http://127.0.0.1:5555
echo  Browser auto-open hobe...
echo  Server bondho korte ei window band korun.
echo.

%PYTHON% app.py
pause