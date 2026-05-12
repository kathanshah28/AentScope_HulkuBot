from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'franka_ai_node'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'scripts'), glob('franka_ai_node/gui.py')),

        (os.path.join('share', package_name, 'scripts', 'stsrc'), glob('franka_ai_node/stsrc/*')),
    ],
    install_requires=[
        'setuptools',
        'flask',
        'requests'
    ],
    zip_safe=True,
    maintainer='kathan',
    maintainer_email='kathanshah2004@gmail.com',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'franka_ai_node = franka_ai_node.main:main',
        ],
    },
)
