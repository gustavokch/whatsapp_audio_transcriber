#!/bin/bash
GUSDIR=$(pwd)
cd $GUSDIR
. ./venv/bin/activate

if [ -f reqs_installed ] && grep -q "^1$" reqs_installed; then
    python whatsapp_handler_refactor.py &
    PID=$!
else
    touch reqs_installed
    pip install -r requirements.txt
    echo "1" > reqs_installed
    python whatsapp_handler_refactor.py &
    PID=$!
fi

# Save the PID to .pidfile
echo $PID > .pidfile
echo "Process started with PID $PID"

# Define cleanup function
cleanup() {
    if [ -f .pidfile ]; then
        KILL_PID=$(cat .pidfile)
        echo "Killing process $KILL_PID"
        kill -9 $KILL_PID
        rm -f .pidfile
    fi
    exit 0
}

# Trap termination signals and run cleanup
trap cleanup SIGINT SIGTERM

# Wait for process to finish
wait $PID
cleanup
