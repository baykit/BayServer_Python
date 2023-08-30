from setuptools import setup, find_packages, findall

print("packages: " + str(find_packages()))

setup(
    name='bayserver',
    version='0.0.1',
    packages=find_packages(),
    author='Michisuke-P',
    author_email='michisukep@gmail.com',
    description='BayServer for Python',
    license='MIT',
    python_requires=">=3.7",
    url='https://baykit.yokohama/',
    package_data={
        'bayserver': [file for file in findall('init')],
        'bayserver': [file for file in findall('conf')],
    },
    install_requires=[
      "importlib_resources",
      "bayserver-core",
      "bayserver-docker-cgi", 
      "bayserver-docker-http3", 
      "bayserver-docker-fcgi", 
      "bayserver-docker-maccaferri", 
      "bayserver-docker-ajp",
      "bayserver-docker-http",
      "bayserver-docker-wordpress"
    ],
    scripts=['bayserver_py'],
    include_package_data = True,
)

