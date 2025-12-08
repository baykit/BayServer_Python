#!/bin/sh
version=`cat VERSION`

major=`echo ${version} | cut -d '.' -f 1`

if [ "$major" != "3" ]; then
  repo=testpypi
else
  repo=pypi
fi

echo version=$version repo=$repo

cd packages
for pkg in `ls` ; do
  pushd . 
  cd $pkg
  twine upload -r ${repo} dist/${pkg}-${version}.tar.gz
  popd
done
