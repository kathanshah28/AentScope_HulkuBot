from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'hulku_ai_agent'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('hulku_ai_agent/config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kathan',
    maintainer_email='kathanshah2004@gmail.com',
    description='Agentic AI controller for HulkuBot with ReAct tool-calling loop',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'agent_node = hulku_ai_agent.agent_node:main',
        ],
    },
)
