#!/bin/bash
. ./venv/bin/activate
python whatsapp_handler_refactor.py &>/tmp/whatsapp_handler.log&
