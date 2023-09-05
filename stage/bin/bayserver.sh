#!/bin/sh
base=`dirname $0`

args=$*
daemon=
for arg in $args; do
  if [ "$arg" = "-daemon" ]; then
    daemon=1
  fi
done

site=${base}/../site-packages
export PYTHONPATH=${site}
if [ "$daemon" = 1 ]; then
   ${site}/bin/bayserver_py $* < /dev/null  > /dev/null 2>&1 &
else
   ${site}/bin/bayserver_py $* 
fi
