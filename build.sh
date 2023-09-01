#!/bin/bash
version=`cat VERSION`

version_file=packages/bayserver-core/bayserver_core/version.py
temp_version_file=/tmp/version.py
sed "s/VERSION=.*/VERSION='${version}'/" ${version_file} > ${temp_version_file}
mv ${temp_version_file} ${version_file}

target_name=BayServer_Python-${version}
target_dir=/tmp/${target_name}
rm -fr ${target_dir}
mkdir ${target_dir}

cp -r stage/* ${target_dir}
cp LICENSE.* NEWS.md README.md ${target_dir}


pkgs="
 bayserver-core
 bayserver-docker-ajp
 bayserver-docker-cgi
 bayserver-docker-fcgi
 bayserver-docker-http
 bayserver-docker-http3
 bayserver-docker-maccaferri
 bayserver-docker-wordpress
 bayserver"


sh ./uninstall.sh
pushd . 

cd packages
for pkg in $pkgs; do
  cd $pkg
  rm -r dist build ${pkg}.egg-info
  rm -r `find  -name "__pycache__"`
  sed -i -e "s/version=.*/version='${version}',/g" setup.py
  python setup.py sdist
  pip install .
  cd ..
done

popd


cd ${target_dir}
bin/bayserver.sh -init

cd /tmp
rm -r `find ${target_name} -name "__pycache__"`
tar czf ${target_name}.tgz ${target_name}

