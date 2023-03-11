#!/bin/bash
version=`cat VERSION`

version_file=core/baykit/bayserver/version.py
temp_version_file=/tmp/version.py
sed "s/VERSION=.*/VERSION='${version}'/" ${version_file} > ${temp_version_file}
mv ${temp_version_file} ${version_file}

target_name=BayServer_Python-${version}
target_dir=/tmp/${target_name}
rm -fr ${target_dir}
mkdir ${target_dir}
mkdir ${target_dir}/lib
cp -r core ${target_dir}/lib
cp -r docker ${target_dir}/lib

cp -r test/simple/lib/conf/* stage/lib/conf
cp -r test/simple/cert stage
cp -r test/simple/www/root stage/www
cp -r test/simple/www/cgi-demo stage/www
cp -r test/simple/www/wsgi-demo stage/www

cp -r stage/* ${target_dir}


cp LICENSE.* NEWS.md README.md ${target_dir}

cd /tmp
rm -r `find ${target_name} -name "__pycache__"`
tar czf ${target_name}.tgz ${target_name}

