# -*- coding: utf-8 -*-
"""

`author`    :   Quentin Lampin <quentin.lampin@orange.com>
`license`   :   MPL
`date`      :   2015/10/05

SensorLab Encapsulation Library
--------------------------
This module provides utility functions to generate SensorLab formatted event reports.

`Requires python 3.2 or above`


"""
import struct
from .frame_format import *

FIRMWARE_PROPERTY_ID = 0x00
STATE_PROPERTY_ID = 0x01


def sensorlab_header(node_id, event_id):
    """
        Builds a SensorLab Header.

        The SensorLab header is the first element of each Sensorlab PCAP record. It defines which node/event is
        described by the record.

        The SensorLab header is 40bits long and its structure is:
            - nodeID    :   4-bytes field. ID of the node which the report relates to
            - eventID   :   1-byte. ID of the reported event

        Possible values for the eventID are:
            - EVENT_NODE_ADD = 0x00
            - EVENT_NODE_PROPERTY_ADD = 0x01
            - EVENT_NODE_PROPERTY_UPDATE = 0x02
            - EVENT_NODE_REMOVE = 0x03
            - EVENT_ENTITY_ADD = 0x10
            - EVENT_ENTITY_PROPERTY_ADD = 0x11
            - EVENT_ENTITY_PROPERTY_UPDATE = 0x12
            - EVENT_ENTITY_REMOVE = 0x13
            - EVENT_LINK_ADD = 0x20
            - EVENT_LINK_PROPERTY_ADD = 0x21
            - EVENT_LINK_PROPERTY_UPDATE = 0x22
            - EVENT_LINK_REMOVE = 0x23
            - EVENT_FRAME_PRODUCE = 0x30
            - EVENT_FRAME_PROPERTY_ADD = 0x31
            - EVENT_FRAME_PROPERTY_UPDATE = 0x32
            - EVENT_FRAME_DATA_UPDATE = 0x33
            - EVENT_FRAME_TX = 0x34
            - EVENT_FRAME_RX = 0x35
            - EVENT_FRAME_CONSUME = 0x36

        Args:
            node_id (unsigned int): node ID
            event_id (unsigned int): event ID

        Returns:
            bytes: the header content


    """
    header = struct.pack("<IB", node_id, event_id)
    return header


def node_add_header(properties_count):
    """
        Builds a SensorLab Node Add Header.

        A node is declared using the Node Add Header (event ID: EVENT_NODE_ADD).
        If propertiesCount > 0, the Node Add header must be followed by the corresponding number of
        PropertyDeclarationPayload.

        The NodeAdd header structure is:
            - propertiesCount   :   1-byte. Number of properties describing the node state.

        Args:
            properties_count (unsigned int): Number of properties describing the node state (up to 255)

        Returns:
            bytes: header content
    """
    header = struct.pack("<B", properties_count)
    return header


def node_property_add_header(properties_count):
    """
        Builds a SensorLab Node Property Add Header.

        A node property is declared using the Node Property Add Header (event ID: EVENT_NODE_PROPERTY_ADD).
        If propertiesCount > 0, the NodePropertyAdd header must be followed by the corresponding number of
        PropertyDeclarationPayload.

        The NodePropertyAdd header structure is:
            - propertiesCount   :   1-byte. Number of properties describing the node state.

        Args:
            properties_count (unsigned int): Number of properties describing the node state (up to 255)

        Returns:
            bytes: header content

    """
    header = struct.pack("<B", properties_count)
    return header


def node_property_update_header(properties_count):
    """
        Builds a SensorLab Node Property Update Header.

        A node property is updated using the Node Property Update Header (event ID: EVENT_NODE_PROPERTY_UPDATE).
        If propertiesCount > 0, the NodePropertyUpdate header must be followed by the corresponding number of
        PropertyUpdatePayload.

        Args:
            properties_count (unsigned int): Number of properties describing the node state (up to 255)

        Returns:
            bytes: header content
    """
    header = struct.pack("<B", properties_count)
    return header


def entity_add_header(entity_id, entity_name_length, properties_count, entity_name):
    """
        Builds a Entity Add Header.

        A node entity is declared using the Entity Add Header (event ID: EVENT_ENTITY_ADD).
        If propertiesCount > 0, the Entity Add header must be followed by the corresponding number of
        PropertyDeclarationPayload.

        The Entity Add Header contains:
            - entity_id             :   1-byte
            - entity_name_length    :   1-byte field
            - properties_count      :   1-byte
            - entity_name           :   Entity's name (variable size)

            Args:
                entity_id (unsigned char): ID of the new entity
                entity_name_length (unsigned int): Entity's name length
                properties_count (unsigned int): Number of properties describing the entity state (up to 255)
                entity_name (string): Name of the entity, ASCII encoded.

            Returns:
                bytes: header content
    """
    header = struct.pack("<BBB", entity_id, entity_name_length, properties_count)
    header += entity_name.encode('ascii')
    return header


def entity_property_add_header(entity_id, properties_count):
    """
        Builds a Entity Property Add Header.

        An entity property is declared using the Entity Property Add Header (event ID: EVENT_ENTITY_PROPERTY_ADD).
        If propertiesCount > 0, the EntityPropertyAdd header must be followed by the corresponding number of
        PropertyDeclarationPayload.

        The EntityPropertyAdd header structure is:
            - entity_id         :  1-byte. ID of the entity.
            - properties_count  :  1-byte. Number of properties describing the entity state.

        Args:
            entity_id (unsigned char): entity ID.
            properties_count (unsigned int): Number of properties describing the entity state (up to 255)

        Returns:
            bytes: header content
    """
    header = struct.pack("<BB", entity_id, properties_count)
    return header


def entity_property_update_header(entity_id, properties_count):
    """
    Builds a Entity Property Update Header.

    An entity property is updated using the Node Property Update Header (event ID: EVENT_ENTITY_PROPERTY_UPDATE).
    If propertiesCount > 0, the NodePropertyUpdate header must be followed by the corresponding number of
    PropertyUpdatePayload.

    The EntityPropertyAdd header structure is:
        - entityID          :   1-byte. ID of the entity.
        - propertiesCount   :   1-byte. Number of properties describing the entity state.

    Args:
        entity_id (unsigned char):
        properties_count (unsigned char)

    Returns:
        bytes: the Entity Property Update header.
    """
    header = struct.pack("<BB", entity_id, properties_count)
    return header


def entity_remove_header(entity_id):
    """
        Builds a Entity Remove Header.

        A node entity is removed using the Entity Remove Header (event ID: EVENT_ENTITY_REMOVE).

        The Entity Remove Header contains:
            - entity_id             :   1-byte. ID of the entity.

            Args:
                entity_id (unsigned char): ID of the new entity

            Returns:
                bytes: header content
    """
    header = struct.pack("<B", entity_id)
    return header


def property_declaration_payload(property_id, unit_prefix, unit, data_type,
                                 property_name_length, property_value_length,
                                 property_name, property_value):
    """
    Builds a Property Declaration Payload.

    The property declaration payload declares a property.

    The PropertyDeclarationPayload structure is:
        - property_id           :  1 byte field. Property ID.
        - unit_prefix           :  1 byte field. Unit prefix.
        - unit                  :  1 byte field. Unit.
        - data_type             :  1 byte field. type of the value.
        - property_name_length  :  1 byte field. length of the property name.
        - property_value_length :  1 byte field. length if the property value
        - property_name         : property_name_length byte(s) field. Property name.
        - property_value        : property_value_length byte(s) field. Property value.

    Args:
        property_id (unsigned char): property ID. Updates refers to this ID instead of the full property name
        unit_prefix (unsigned char): unit prefix, e.g. *milli* as in mW
        unit (unsigned char): unit, e.g. Watts
        data_type (unsigned char): type of value, e.g. uint8
        property_name_length (unsigned int): name length of the property
        property_value_length (unsigned int): length of the property value in bytes, e.g. 4 for a uint32
        property_name (string): property name
        property_value: property value

    Returns:
        bytes: payload content
    """

    payload = struct.pack("<BBBBBH", property_id, unit_prefix, unit, data_type,
                          property_name_length, property_value_length)
    payload += property_name.encode('ascii')
    payload += format_property_value(property_value, data_type)
    return payload


def property_reference_payload(property_id, data_type, property_value_length, property_value):
    """
    Builds a Property Reference Payload.

    The property reference payload describes a property update.

    The PropertyReferencePayload structure is:
        - property_id           :  1 byte field. Property ID.
        - data_type             :  1 byte field. type of the value.
        - property_value_length :  1 byte field. length if the property value
        - property_value        : property_value_length byte(s) field. Property value.

    Args:
        property_id (unsigned char): property ID. Updates refers to this ID instead of the full property name
        data_type (unsigned char): type of value, e.g. uint8
        property_value_length (unsigned int): length of the property value in bytes, e.g. 4 for a uint32
        property_value: property value

    Returns:
        bytes: payload content
    """
    payload = struct.pack("<BH", property_id, property_value_length)
    payload += format_property_value(property_value, data_type)
    return payload


def link_add_header(entity_id, link_id, source_properties_count, target_properties_count, link_properties_count):
    """
    Builds a Link Add Header

    The link add header declares a link between two nodes entities (event EVENT_LINK_ADD).

    The LinkAddHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - link_id                   : 1 byte field. Link ID.
        - source_properties_count   : 1 byte field. Number of properties that describe the source/origin of the link.
        - target_properties_count   : 1 byte field. Number of properties that describe the target of the link.
        - link_properties_count     : 1 byte field. Number of properties that describe the link.

    Args:
        entity_id (unsigned char): entity ID.
        link_id (unsigned char): Link ID.
        source_properties_count (unsigned int): source properties count.
        target_properties_count (unsigned int): target properties count.
        link_properties_count (unsigned int): link properties count.

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBBBB", entity_id, link_id,
                         source_properties_count, target_properties_count, link_properties_count)
    return header


def link_property_add_header(entity_id, link_id, link_properties_count):
    """
    Builds a Link Property Add Header

    The link property add header declares a link property (event EVENT_LINK_PROPERTY_ADD).

    The LinkPropertyAddHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - link_id                   : 1 byte field. Link ID.
        - link_properties_count     : 1 byte field. Number of properties that describe the link.

    Args:
        entity_id (unsigned char): Entity ID.
        link_id (unsigned char): Link ID.
        link_properties_count (unsigned int): link properties count.

    Returns:

    """
    header = struct.pack("<BBB", entity_id, link_id, link_properties_count)
    return header


def link_property_update_header(entity_id, link_id, link_properties_count):
    """
    Builds a Link Property Update Header

    The link property update header describes a link property update (event EVENT_LINK_PROPERTY_UPDATE).

    The LinkPropertyUpdateHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - link_id                   : 1 byte field. Link ID.
        - link_properties_count     : 1 byte field. Number of properties that describe the link.

    Args:
        entity_id (unsigned char): Entity ID.
        link_id (unsigned char): Link ID.
        link_properties_count (unsigned int): link properties count.

    Returns:

    """
    header = struct.pack("<BBB", entity_id, link_id, link_properties_count)
    return header


def link_remove_header(entity_id, link_id):
    """
    Builds a Link Add Header

    The link remove header declares a link removal (event EVENT_LINK_REMOVE).

    The LinkRemoveHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - link_id                   : 1 byte field. Link ID.

    Args:
        entity_id (unsigned char): entity ID
        link_id (unsigned char): Link ID

    Returns:
        bytes: header content

    """
    header = struct.pack("<BB", entity_id, link_id)
    return header


def frame_produce_header(entity_id, frame_id, data_length, properties_count):
    """
    Builds a Frame Produce Header.

    The frame produce header declares a frame production (event EVENT_FRAME_PRODUCE).

    The FrameProduceHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - frame_id                  : 1 byte field. Frame ID.
        - data_length               : 2 bytes field. Frame length.
        - properties_count          : 1 byte field. Frame properties count.

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        data_length (unsigned int): frame content length
        properties_count: frame properties count

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBHB", entity_id, frame_id, data_length, properties_count)
    return header


def frame_receive_header(entity_id, frame_id, data_length, properties_count):
    """
    Builds a Frame Receive Header.

    The frame receive header declares a frame reception (event EVENT_FRAME_RX).

    The FrameReceiveHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - frame_id                  : 1 byte field. Frame ID.
        - data_length               : 2 bytes field. Frame length.
        - properties_count          : 1 byte field. Frame properties count.

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        data_length (unsigned int): frame content length
        properties_count: frame properties count

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBHB", entity_id, frame_id, data_length, properties_count)
    return header


def frame_property_add_header(entity_id, frame_id, properties_count):
    """
    Builds a Frame Property Add Header

    The frame property add header declares a link property (event EVENT_FRAME_PROPERTY_ADD).

    The FramePropertyAddHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - frame_id                   : 1 byte field. Link ID.
        - properties_count     : 1 byte field. Number of properties that describe the frame.

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        properties_count: frame properties count

    Returns:

    """
    header = struct.pack("<BBB", entity_id, frame_id, properties_count)
    return header


def frame_property_update_header(entity_id, frame_id, properties_count):
    """
    Builds a Frame Property Update Header

    The frame property update header describes a frame property update (event EVENT_FRAME_PROPERTY_UPDATE).

    The FramePropertyUpdateHeader structure is:
        - entity_id                 : 1 byte field. Entity ID.
        - frame_id                  : 1 byte field. Link ID.
        - properties_count          : 1 byte field. Number of properties that describe the frame.

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        properties_count: frame properties count

    Returns:

    """
    header = struct.pack("<BBB", entity_id, frame_id, properties_count)
    return header


'''
 Frame Data Update Header
 ----------------
'''


def frame_data_update_header(entity_id, frame_id, data_length):
    """
    Builds a Frame Data Update Header

    The frame data update header describes an update of the frame content (event EVENT_FRAME_DATA_UPDATE).

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        data_length (unsigned int): data length

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBH", entity_id, frame_id, data_length)
    return header


def frame_transmit_header(entity_id, frame_id, data_length):
    """
    Builds a Frame Transmit Header

    The frame transmit header describes a frame transmission (event EVENT_FRAME_TX).

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        data_length (unsigned int): data length

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBH", entity_id, frame_id, data_length)
    return header


def frame_consume_header(entity_id, frame_id, data_length):
    """
    Builds a Frame Consume Header

    The frame consume header describes a frame consumption (event EVENT_FRAME_CONSUME).

    Args:
        entity_id (unsigned char): entity ID
        frame_id (unsigned char): frame ID
        data_length (unsigned int): data length

    Returns:
        bytes: header content

    """
    header = struct.pack("<BBH", entity_id, frame_id, data_length)
    return header

frameConsumeHeader = frame_data_update_header


def format_property_value(property_value, data_type):
    """

    Args:
        property_value (bytes or str): property value
        data_type (unsigned char): value type

    Returns:
        bytes: value

    """
    payload = None
    if data_type == TYPE_BOOLEAN:
        payload = struct.pack("?", property_value)
    if data_type == TYPE_INT8:
        payload = struct.pack("b", property_value)
    if data_type == TYPE_INT16:
        payload = struct.pack("h", property_value)
    if data_type == TYPE_INT32:
        payload = struct.pack("i", property_value)
    if data_type == TYPE_INT64:
        payload = struct.pack("q", property_value)
    if data_type == TYPE_UINT8:
        payload = struct.pack("B", property_value)
    if data_type == TYPE_UINT16:
        payload = struct.pack("H", property_value)
    if data_type == TYPE_UINT32:
        payload = struct.pack("I", property_value)
    if data_type == TYPE_UINT64:
        payload = struct.pack("Q", property_value)
    if data_type == TYPE_FLOAT:
        payload = struct.pack("f", property_value)
    if data_type == TYPE_DOUBLE:
        payload = struct.pack("d", property_value)
    if data_type == TYPE_ASCII_ARRAY:
        payload = property_value.encode('ascii')
    if data_type == TYPE_BYTE_ARRAY:
        payload = property_value
    if data_type == TYPE_INVALID:
        payload = property_value
    return payload
