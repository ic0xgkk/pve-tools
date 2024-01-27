#!/bin/bash

t=`date +"%Y-%m-%d %H:%M:%S"`

echo "* time: $t" > /opt/logs/graceful_shutdown.log

(/bin/python3 /opt/scripts/graceful_shutdown.py || true) >> /opt/logs/graceful_shutdown.log 2>&1

(/bin/python3 /opt/scripts/graceful_shutdown.py || true) >> /opt/logs/graceful_shutdown.log 2>&1

/sbin/poweroff
