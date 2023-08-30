from setuptools import setup, find_packages

print("packages: " + str(find_packages()))

setup(
    name='bayserver-docker-wordpress',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        # Dependencies if any
    ],
    author='Michisuke-P',
    author_email='michisukep@gmail.com',
    description='WordPress docker for BayServer',
    license='MIT',
    python_requires=">=3.7",
    url='https://baykit.yokohama/',
)

