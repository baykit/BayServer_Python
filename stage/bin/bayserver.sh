#!/bin/sh
base=`dirname $0`

args=$*
daemon=
for arg in $args; do
  if [ "$arg" = "-daemon" ]; then
    daemon=1
  fi
done

pycmd=python
pyver=`python --version 2>&1 | sed 's/Python //' | sed 's/\..*//'`
if [ "$pyver" != "3" ]; then
   pycmd=python3
fi

if [ "$daemon" = 1 ]; then
   $pycmd $base/bootstrap.py $* < /dev/null  > /dev/null 2>&1 &
else
   $pycmd $base/bootstrap.py $* 
fi
