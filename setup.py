from setuptools import setup

setup(
    name='Instagram Monitor',
    version='0.1',
    author='Jose Sebastián Canós',
    author_email='elpoliticamentecorrecto@gmail.com',
    packages=['instagram_monitor'],
    install_requires=['networkx', 'pymongo', 'requests'],
    dependency_links=['https://codeload.github.com/ping/instagram_private_api/tar.gz/1.3.3'],
    entry_points={'console_scripts': 
        ['instagram_monitor = instagram_monitor.__main__:main']})