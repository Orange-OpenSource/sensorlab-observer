# -*- coding: utf-8 -*-
"""
`author`	:	Quentin Lampin <quentin.lampin@orange.com>
`license`	:	MPL
`date`		:	2015/10/05

PCAP Encapsulation Library
--------------------------
This module provides utility functions to generate PCAP formatted files.

`Requires python 3.2 or above`

"""

import struct


def pcap_global_header(network):
    """
    Generate a PCAP Global Header with given network field.

    The PCAP global header is 24bytes long and its structure is:

    - magicNumber			: 	4-bytes constant sequence, used by the PCAP parser
                                to determine the endianness of the file
                                (here, represented in its little-endian form: D4 C3 B2 A1)
    - versionNumberMajor	:	2-bytes field, PCAP major version of the file, here 2 (00 02)
    - versionNumberMajor	:	2-bytes field, PCAP minor version of the file, here 4 (00 04)
    - thisZone				:	4-bytes field, timezone used to record the capture, here GMT (00 00 00 00)
    - sigFigs				:	4-bytes field, accuracy of the timestamps in the capture, set to (00 00 00 00)
    - snapLen				:	4-bytes field, maximum size of capture packets, here 65535 (FF FF 00 00)
    - network				:	4-bytes field, link-layer type ID, set by the user, e.g. (D7 00 00 00) for SensorLab
                                or (01 00 00 00) for ethernet

    Args:
        network (unsigned int): the network ID, i.e. link-layer type ID.

    Returns:
        bytes: the PCAP Global header.
    """
    header = b'\xD4\xC3\xB2\xA1' \
             + b'\x02\x00' \
             + b'\x04\x00' \
             + b'\x00\x00\x00\x00' \
             + b'\x00\x00\x00\x00' \
             + b'\xFF\xFF\x00\x00' \
             + struct.pack("<I", network)
    return header


def pcap_record(time_s, time_us, data):
    """
    Generate a PCAP Record (header+data) with given date and data.
    The PCAP record header is 16bytes long and its structure is:

    - time_s				:	timestamp of the packet in seconds, expressed as seconds elapsed since the UNIX epoch
    - time_us 				:	microseconds elapsed since tsSec timestamp
    - incl_length			:	length of the packet capture in bytes
    - orig_length			:	original size of the packet captured in bytes

    Args:
        time_s (unsigned int): timestamp of the packet in seconds, expressed as seconds elapsed since the UNIX epoch
        time_us (unsigned int): microseconds elapsed since time_us timestamp
        data (bytes): packet content

    Returns:
        bytes: the PCAP Packet

    """
    header = struct.pack("<IIII", time_s, time_us, len(data), len(data))
    return header + data


class PCAPCapture:
    """
    Wrapper around a file output to generate a PCAP capture.

    A PCAP captures starts with a PCAP global header, followed by PCAP records.
    """

    def __init__(self, output_name, network):
        """
            create a new PCAP capture file.

            Args:
                output_name (str): capture file name
                network (str): network ID, i.e. link-layer type ID

            Raises:
                FileError: exceptions raised by the underlying file object
        """
        try:
            self.output = open(output_name, 'wb')
        except Exception as e:
            raise e

        file_header = pcap_global_header(network)
        self.output.write(file_header)

    def write_record(self, time_s, time_us, data):
        """
        Write a PCAP record to the capture file.

        Args:
            time_s (unsigned int): timestamp of the packet in seconds, expressed as seconds elapsed since the UNIX epoch
            time_us (unsigned int): microseconds elapsed since time_us timestamp
            data (bytes): packet content

        Raises:
            FileError: exceptions raised by the underlying file object
        """

        record = pcap_record(time_s, time_us, data)
        try:
            self.output.write(record)
        except Exception as e:
            raise e

    def close(self):
        """
        Close the output file.
        """
        self.output.close()
