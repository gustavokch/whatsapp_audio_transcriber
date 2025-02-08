#!/bin/bash
cd $GUSDIR
. ./venv/bin/activate

if [ -f reqs_installed ] && grep -q "^1$" reqs_installed; then
    python whatsapp_handler_refactor.py
else
    touch reqs_installed
    pip install -r requirements.txt
    echo "1" > reqs_installed
    python whatsapp_handler_refactor.py
fi
