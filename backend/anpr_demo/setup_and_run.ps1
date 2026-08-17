$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (!(Test-Path '.venv/Scripts/python.exe')) {
    Write-Host 'Creating virtual environment...'
    C:/Python313/python.exe -m venv .venv
}

Write-Host 'Installing Python dependencies...'
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ultralytics pandas opencv-python numpy scipy easyocr filterpy

if (!(Test-Path 'sort')) { New-Item -ItemType Directory -Path 'sort' | Out-Null }
if (!(Test-Path 'models')) { New-Item -ItemType Directory -Path 'models' | Out-Null }

if (!(Test-Path 'sort/sort.py')) {
    Write-Host 'Downloading SORT tracker...'
    curl.exe -L "https://raw.githubusercontent.com/abewley/sort/master/sort.py" -o "sort/sort.py"
}
if (!(Test-Path 'sort/__init__.py')) {
    Set-Content -Path 'sort/__init__.py' -Value 'from .sort import *'
}

if (!(Test-Path 'models/license_plate_detector.pt')) {
    Write-Host 'Downloading free license plate detector model...'
    curl.exe -L "https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt" -o "models/license_plate_detector.pt"
}

if (!(Test-Path 'sample.avi')) {
    Write-Host 'Downloading free sample video...'
    curl.exe -L "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/vtest.avi" -o "sample.avi"
}

Write-Host 'Running ANPR pipeline...'
.\.venv\Scripts\python.exe main.py --video sample.avi --plate-model models/license_plate_detector.pt --output-csv test.csv
