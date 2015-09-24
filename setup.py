from setuptools import setup, find_packages


setup(
    name='stacktask',

    version='0.1.1a1',
    description='A user task service for openstack.',
    long_description=(
        'A task service to sit alongside keystone and ' +
        'add some missing functionality.'),
    url='https://github.com/catalyst/stack-task',
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
    package_data={'stacktask': ['api/v*/templates/*.txt']},

    install_requires=[
        'Django>=1.7.3',
        'djangorestframework>=3.0.3',
        'decorator>=3.4.0',
        'jsonfield>=1.0.2',
        'keystonemiddleware>=1.3.1',
        'python-keystoneclient>=1.0.0',
        'python-neutronclient>=2.3.10',
        'pyyaml>=3.11',
        'django-rest-swagger>=0.3.3'
    ],
    entry_points={
        'console_scripts': [
            'stacktask = stacktask:management_command',
        ],
    }
)
