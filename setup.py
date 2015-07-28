from setuptools import setup, find_packages


setup(
    name='stacktask',

    version='0.1.0a4',
    description='A user registration service for openstack.',
    long_description=(
        'A registration service to sit alongside keystone and ' +
        'add some missing functionality.'),
    url='https://github.com/catalyst/openstack-registration',
    author='Adrian Turjak',
    author_email='adriant@catalyst.net.nz',
    license='Apache 2.0',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='openstack registration keystone users tasks workflow',

    packages=find_packages(),

    install_requires=[
        'Django>=1.7.3',
        'djangorestframework>=3.0.3',
        'decorator>=3.4.0',
        'jsonfield>=1.0.2',
        'keystonemiddleware>=1.3.1',
        'python-keystoneclient>=1.0.0',
        'python-neutronclient>=2.3.10',
        'pyyaml>=3.11'
    ],
    entry_points={
        'console_scripts': [
            'stacktask = stacktask:management_command',
        ],
    }
)
