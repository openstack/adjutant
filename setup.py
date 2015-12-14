from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.readlines()

setup(
    name='stacktask',

    version='0.1.1a3',
    description='A user task service for openstack.',
    long_description=(
        'A task service to sit alongside keystone and ' +
        'add some missing functionality.'),
    url='https://github.com/catalyst/stacktask',
    author='Adrian Turjak',
    author_email='adriant@catalyst.net.nz',
    license='Apache 2.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='openstack keystone users tasks registration workflow',

    packages=find_packages(),
    package_data={
        'stacktask': [
            'api/v*/templates/*.txt',
            'notifications/templates/*.txt',
            'notifications/*/templates/*.txt']},
    install_requires=required,
    entry_points={
        'console_scripts': [
            'stacktask = stacktask:management_command',
        ],
    }
)
