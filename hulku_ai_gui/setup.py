from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'hulku_ai_gui'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    package_data={
        package_name: [
            'templates/*.html',
            'static/**/*',
        ],
    },
    include_package_data=True,
    install_requires=['setuptools', 'flask'],
    zip_safe=True,
    maintainer='kathan',
    maintainer_email='kathanshah2004@gmail.com',
    description='Flask GUI for the HulkuBot AI Agent',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'main = hulku_ai_gui.main:main',
        ],
    },
)
