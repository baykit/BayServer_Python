from setuptools import setup, find_packages

print("packages: " + str(find_packages()))

setup(
    name='bayserver-docker-fcgi',
    version='2.2.1',
    packages=find_packages(),
    package_data={
        '': ['LICENSE.BAYKIT', 'README.md'],
    },  
    install_requires=[
      "bayserver-core==2.2.1",
    ],
    author='Michisuke-P',
    author_email='michisukep@gmail.com',
    description='FCGI Docker for BayServer',
    license='MIT',
    python_requires=">=3.7",
    url='https://baykit.yokohama/',
)

