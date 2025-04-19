@echo off
echo Installing dependencies...
pip install -r requirements.txt
pip install uvicorn[standard]

echo Starting server...
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
pause 