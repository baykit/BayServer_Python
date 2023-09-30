#!/bin/sh

cd packages
for pkg in `ls` ; do
  pushd . 
  cd $pkg
  rm -r build *.egg-info
  popd
done
