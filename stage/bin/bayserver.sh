#!/bin/sh
base=`dirname $0`

args=$*
daemon=
for arg in $args; do
  if [ "$arg" = "-daemon" ]; then
    daemon=1
  fi
done


if [ "$daemon" = 1 ]; then
   bayserver_py $* < /dev/null  > /dev/null 2>&1 &
else
   bayserver_py $* 
fi
