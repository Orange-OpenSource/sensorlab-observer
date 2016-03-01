# -*- coding: utf-8 -*-
"""
Sensorlab node setup module.

`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/12
Copyright 2015 Orange

# Overview
-----------
This module handles the node setup procedure.

## Node Setup
--------------
The node is configured via the `node-setup` command.
This `setup` command is sent to the module as a HTTP POST request containing one argument:

    - `node_configuration`: the module configuration archive.

### Node configuration archive
-------------------------------
The configuration archive is of type **tar.gz** and contains the following directories and files:

    - `controller/`: configuration files and executables used by the node controller.

        - `executables/`: executables used in control commands.

        - `configuration_files/`: executables configuration files.

    - `serial/`: contains the python module that reports frames sent on the serial interface.

    - `manifest.yml`: controller command lines and serial configuration file.

### Manifest.yml
-----------------
The manifest file complies to the YAML specification.
It must contain the following structure: 

    - controller:
        - commands:
            - load 		:	load a firmware into the node
            - start 	: 	start the node
            - stop 		:	stop the node
            - reset     :	reset the node

        - executables:
            - id 		:	executable ID
              file 		:	executable
              brief		: 	executable short description
            - ...

        - configuration_files
            - id 		:	configuration file ID
              file 		:	configuration file
              brief		: 	configuration file short description
            - ...

    - serial:
        - port 		:    the serial port
        - baudrate	:    serial interface baudrate
        - parity 	:    parity bits
        - stopbits 	:    stop bits
        - bytesize 	:    byte word size
        - rtscts	:    RTS/CTS
        - xonxoff	:    XON/XOFF
        - timeout	:    timeout of the read action
        - module 	:    name of the module that handles serial frames

Controller commands may contain two types of placeholders :
    - executable placeholders			: identified by a <!name> tag where name is the executable ID.
    - configuration file placeholders	: identified by a <#name> tag where name is the configuration file ID.

Placeholders are resolved when the manifest is parsed for the first time. 


"""
import os
import tempfile
import tarfile
import yaml
import shutil

from ..m_common import m_common

# configuration archive filename
CONFIGURATION_FILENAME = 'node-profile.tar.gz'

# archive members
CONTROLLER_SUBDIR = 'controller'
CONTROLLER_EXECUTABLES_SUBDIR = 'controller/executables'
CONTROLLER_CONFIGURATION_FILES_SUBDIR = 'controller/configuration_files'
SERIAL_SUBDIR = 'serial'
CONFIGURATION_MANIFEST = 'manifest.yml'
CONFIGURATION_MANDATORY_MEMBERS = [
    CONTROLLER_SUBDIR,
    CONTROLLER_EXECUTABLES_SUBDIR,
    CONTROLLER_CONFIGURATION_FILES_SUBDIR,
    SERIAL_SUBDIR,
    CONFIGURATION_MANIFEST
]

# manifest members
MANIFEST_MANDATORY_MEMBERS = [
    'controller',
    'controller/commands',
    'controller/commands/load',
    'controller/commands/start',
    'controller/commands/stop',
    'controller/commands/reset',
    'controller/configuration_files',
    'serial',
    'serial/port',
    'serial/baudrate',
    'serial/parity',
    'serial/stopbits',
    'serial/bytesize',
    'serial/rtscts',
    'serial/xonxoff',
    'serial/timeout',
    'serial/module'
]


class Loader:
    def __init__(self, profile_archive):

        # create a temporary directory and extract the content of the archive
        self.temp_directory = tempfile.mkdtemp()
        archive_path = os.path.join(self.temp_directory, CONFIGURATION_FILENAME)
        profile_archive.save(archive_path)
        archive = tarfile.open(archive_path)

        # validate the archive content
        archive_contents = archive.getnames()
        if any(elt not in archive_contents for elt in CONFIGURATION_MANDATORY_MEMBERS):
            # invalid archive content, raise an exception
            missing_arguments = filter(lambda argument: argument not in archive_contents,
                                       CONFIGURATION_MANDATORY_MEMBERS)
            raise m_common.NodeSetupException(m_common.ERROR_CONFIGURATION_MISSING_ARGUMENT.format(missing_arguments))

        # decompress the archive
        archive.extractall(self.temp_directory)

        # read the manifest
        with open(os.path.join(self.temp_directory, CONFIGURATION_MANIFEST), 'r') as self.manifest_file:
            self.manifest = yaml.load(self.manifest_file.read())

        # validate the manifest
        for path in MANIFEST_MANDATORY_MEMBERS:
            iterator = self.manifest
            path_elements = path.split('/')
            for element in path_elements:
                try:
                    iterator = iterator[element]
                except:
                    raise m_common.NodeSetupException(m_common.ERROR_CONFIGURATION_MISSING_ARGUMENT.format(element))

        # replace placeholders and complete path names in executables entries
        if self.manifest['controller']['executables']:
            for executable in self.manifest['controller']['executables']:
                eid = executable['id']
                efile = executable['file']
                executables_dir = os.path.join(self.temp_directory, CONTROLLER_EXECUTABLES_SUBDIR)
                for cmd_name, cmd in self.manifest['controller']['commands']:
                    self.manifest['controller']['commands'][cmd_name] = \
                        cmd.replace('<!{0}>'.format(eid), os.path.join(executables_dir, efile))

        # replace placeholders and complete path names in configuration file entries
        if self.manifest['controller']['configuration_files']:
            for configuration_file in self.manifest['controller']['configuration_files']:
                cid = configuration_file['id']
                cfile = configuration_file['file']
                configuration_files_dir = os.path.join(self.temp_directory, CONTROLLER_CONFIGURATION_FILES_SUBDIR)
                for cmd_name, cmd in self.manifest['controller']['commands'].items():
                    self.manifest['controller']['commands'][cmd_name] = \
                        cmd.replace('<#{0}>'.format(cid), os.path.join(configuration_files_dir, cfile))

        serial_directory = os.path.join(self.temp_directory, SERIAL_SUBDIR)
        self.manifest['serial']['module'] = os.path.join(serial_directory, self.manifest['serial']['module'])

    def clean(self):
        shutil.rmtree(self.temp_directory)
