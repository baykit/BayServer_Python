from setuptools import setup, find_packages, findall

print("packages: " + str(find_packages()))

setup(
    name='bayserver',
    version='2.2.1',
    packages=find_packages(),
    author='Michisuke-P',
    author_email='michisukep@gmail.com',
    description='BayServer for Python',
    license='MIT',
    python_requires=">=3.7",
    url='https://baykit.yokohama/',
    package_data={
    },
    install_requires=[
      "bayserver-core==2.2.1",
      "bayserver-docker-cgi==2.2.1", 
      "bayserver-docker-http3==2.2.1", 
      "bayserver-docker-fcgi==2.2.1", 
      "bayserver-docker-maccaferri==2.2.1", 
      "bayserver-docker-ajp==2.2.1",
      "bayserver-docker-http==2.2.1",
      "bayserver-docker-wordpress==2.2.1",
    ],
    scripts=['bayserver_py'],
    include_package_data = True,
)

