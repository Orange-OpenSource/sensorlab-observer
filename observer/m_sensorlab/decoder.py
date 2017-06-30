import struct
import traceback
import sys

from itertools import repeat


from .. import m_common


EVENTS = {
    0x00: {'title': 'NodeAdd'},
    0x01: {'title': 'NodePropertyAdd'},
    0x02: {'title': 'NodePropertyUpdate'},
    0x03: {'title': 'NodeRemove'},
    0x10: {'title': 'EntityAdd'},
    0x11: {'title': 'EntityPropertyAdd'},
    0x12: {'title': 'EntityPropertyUpdate'},
    0x13: {'title': 'EntityRemove'},
    0x20: {'title': 'LinkAdd'},
    0x21: {'title': 'LinkPropertyAdd'},
    0x22: {'title': 'LinkPropertyUpdate'},
    0x23: {'title': 'LinkRemove'},
    0x30: {'title': 'FrameProduce'},
    0x31: {'title': 'FramePropertyAdd'},
    0x32: {'title': 'FramePropertyUpdate'},
    0x33: {'title': 'FrameDataUpdate'},
    0x34: {'title': 'FrameTx'},
    0x35: {'title': 'FrameRx'},
    0x36: {'title': 'FrameConsume'}
}

PROPERTIES = {
    0x00: {'title': 'boolean', 'format': '?'},
    0x01: {'title': 'int8', 'format': 'b'},
    0x02: {'title': 'int16', 'format': 'h'},
    0x03: {'title': 'int32', 'format': 'i'},
    0x04: {'title': 'int64', 'format': 'q'},
    0x05: {'title': 'uint8', 'format': 'B'},
    0x06: {'title': 'uint16', 'format': 'H'},
    0x07: {'title': 'uint32', 'format': 'I'},
    0x08: {'title': 'uint64', 'format': 'Q'},
    0x09: {'title': 'float', 'format': 'f'},
    0x0A: {'title': 'double', 'format': 'd'},
    0x0B: {'title': 'asciiArray', 'format': None},
    0x0C: {'title': 'byteArray', 'format': None},
    0x0D: {'title': 'invalid', 'format': None},
    0x0E: {'title': 'floatArray', 'format': None},
    0x0F: {'title': 'doubleArray', 'format': None}

}

PREFIXES = {
    0x00: 'Y',
    0x01: 'Z',
    0x02: 'E',
    0x03: 'P',
    0x04: 'T',
    0x05: 'G',
    0x06: 'M',
    0x07: 'k',
    0x08: 'h',
    0x09: 'da',
    0x0A: '',
    0x0B: 'd',
    0x0C: 'c',
    0x0D: 'm',
    0x0E: 'u',
    0x0F: 'n',
    0x10: 'p',
    0x11: 'f',
    0x12: 'a',
    0x13: 'z',
    0x14: 'y',
}
UNITS = {
    0x00: '',
    0x01: 'm',
    0x02: 'kg',
    0x03: 's',
    0x04: 'A',
    0x05: 'K',
    0x06: 'M',
    0x07: 'Cd',
    0x08: 'rad',
    0x09: 'sr',
    0x0A: 'Hz',
    0x0B: 'N',
    0x0C: 'Pa',
    0x0D: 'J',
    0x0E: 'W',
    0x0F: 'C',
    0x10: 'V',
    0x11: 'F',
    0x12: 'Ohm',
    0x13: 'S',
    0x14: 'Wb',
    0x15: 'T',
    0x16: 'H',
    0x17: 'C',
    0x18: 'lm',
    0x19: 'lx',
    0x1A: 'Bq',
    0x1B: 'Gy',
    0x1C: 'Sv',
    0x1D: 'kat',
    0x1E: 'dB',
    0x1F: 'dBW',
    0x20: 'dBm'
}

UNKNOWN_EVENT_ID = "unknown event ID: {0}"
UNKNOWN_ENTITY_ID = "unknown entity ID: {0}"
UNKNOWN_PROPERTY_ID = "unknown property ID: {0}"
UNKNOWN_LINK_ID = "unknown link ID: {0} at entity {1}"
UNKNOWN_FRAME_ID = "unknown frame ID: {0} at entity {1}"
UNKNOWN_FRAME_ENTITY_ID = "unknown entity ID: {0} for frame ID {1}"

DECODER_BINARY = "binary format invalid in: {0}"
DECODER_ASCII_ERROR = "non-ASCII character in: {0}"
DECODER_FLOAT_ARRAY_ERROR = "invalid float array format in: {0}"
DECODER_DOUBLE_ARRAY_ERROR = "invalid double array format in: {0}"


def block_decode(block_format, buffer, offset=0):
    size = struct.calcsize(block_format)
    return (
        struct.unpack_from(block_format, buffer, offset),
        offset + size
    )


def property_declaration_decode(buffer, json, offset, declarations):
    try:
        decoded = block_decode("<BBBBBH", buffer, offset)
        ((property_id, prefix, unit, data_type, property_name_length, property_value_length), offset,) = decoded
        property_name = buffer[offset:offset + property_name_length].decode('ascii')
        offset += property_name_length
    except struct.error:
        raise m_common.DecoderException(DECODER_BINARY.format(
            ' '.join([hex(b)[2:] for b in buffer[offset:offset+struct.calcsize("<BBBBBH")]]))
        )
    except UnicodeDecodeError:
        raise m_common.DecoderException(DECODER_ASCII_ERROR.format(buffer[offset:offset + property_name_length]))

    if PROPERTIES[data_type]['format']:
        try:
            data_decoded = block_decode(PROPERTIES[data_type]['format'], buffer, offset)
            ((property_value,), offset) = data_decoded
        except struct.error:
            raise m_common.DecoderException(DECODER_BINARY.format(
                ' '.join([hex(b)[2:] for b in buffer[offset:struct.calcsize(PROPERTIES[data_type]['format'])]]))
            )

    elif PROPERTIES[data_type]['title'] is 'asciiArray':
        try:
            property_value = buffer[offset:offset + property_value_length].decode('ascii')
            offset += property_value_length
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_ASCII_ERROR.format(buffer[offset:offset + property_value_length])
            )

    elif PROPERTIES[data_type]['title'] is 'byteArray':
        property_value = ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]])
        offset += property_value_length
    
    ###
    elif PROPERTIES[data_type]['title'] is 'floatArray':
        try:

            property_value = struct.unpack('%sf' %int(property_value_length/4),buffer[offset:offset + property_value_length])
            offset += (property_value_length)
        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_FLOAT_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
            )
        ###

    elif PROPERTIES[data_type]['title'] is 'doubleArray':
        try:

            property_value = struct.unpack('%sd' %int(property_value_length/8),buffer[offset:offset + property_value_length])
            offset += (property_value_length)
        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_DOUBLE_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
        ###
            )
       
    else:  # 'invalid'
        property_value = '!' + ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]]) + '!'
        offset += property_value_length

    json[property_name] = {'value': property_value, 'prefix': PREFIXES[prefix], 'unit': UNITS[unit]}

    declarations[property_id] = {'title': property_name, 'type': PROPERTIES[data_type]['title'],
                                 'prefix': PREFIXES[prefix], 'unit': UNITS[unit],
                                 'format': PROPERTIES[data_type]['format']}

    return offset


########################## 
def property_reference_decode_node_update(buffer, json, offset, declarations):
    try:
        decoded = block_decode("<BI", buffer, offset)
        ((property_id, property_value_length), offset,) = decoded
    except struct.error:
        raise m_common.DecoderException(DECODER_BINARY.format(
            ' '.join([hex(b)[2:] for b in buffer[offset:offset+struct.calcsize("<BI")]]))
        )
    
    if not declarations[property_id]:
        # raise exception
        raise m_common.DecoderException(UNKNOWN_PROPERTY_ID.format(property_id))

    property_name = declarations[property_id]['title']
    prefix = declarations[property_id]['prefix']
    unit = declarations[property_id]['unit']
    data_type = declarations[property_id]['type']
    data_format = declarations[property_id]['format']

    if data_format:
        try:
            data_decoded = block_decode(data_format, buffer, offset)
            ((property_value,), offset,) = data_decoded
        except struct.error:
            raise m_common.DecoderException(DECODER_BINARY.format(
                ' '.join([hex(b)[2:] for b in buffer[offset:offset + struct.calcsize(data_format)]]))
            )

    elif data_type is 'asciiArray':
        try:
            property_value = buffer[offset:offset + property_value_length].decode('ascii')
            offset += property_value_length
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_ASCII_ERROR.format(buffer[offset:offset + property_value_length])
            )

    elif data_type is 'byteArray':
        property_value = ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]])
        offset += property_value_length
    
    elif data_type is 'floatArray':
        try:

            property_value = struct.unpack('%sf' %int(property_value_length/4),buffer[offset:offset + property_value_length])
            offset += (property_value_length)

        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_FLOAT_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
        ###
            )
    elif data_type is 'doubleArray':
        try:

            property_value = struct.unpack('%sd' %int(property_value_length/8),buffer[offset:offset + property_value_length])
            offset += (property_value_length)
        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_DOUBLE_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
        ###
            )

    else:  # 'invalid'
        property_value = '!' + ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]]) + '!'
        offset += property_value_length

    json[property_name] = {'value': property_value, 'prefix': prefix, 'unit': unit}

    return offset

######################
def property_reference_decode(buffer, json, offset, declarations):
    try:
        decoded = block_decode("<BH", buffer, offset)
        ((property_id, property_value_length), offset,) = decoded
    except struct.error:
        raise m_common.DecoderException(DECODER_BINARY.format(
            ' '.join([hex(b)[2:] for b in buffer[offset:offset+struct.calcsize("<BH")]]))
        )
    
    if not declarations[property_id]:
        # raise exception
        raise m_common.DecoderException(UNKNOWN_PROPERTY_ID.format(property_id))

    property_name = declarations[property_id]['title']
    prefix = declarations[property_id]['prefix']
    unit = declarations[property_id]['unit']
    data_type = declarations[property_id]['type']
    data_format = declarations[property_id]['format']

    if data_format:
        try:
            data_decoded = block_decode(data_format, buffer, offset)
            ((property_value,), offset,) = data_decoded
        except struct.error:
            raise m_common.DecoderException(DECODER_BINARY.format(
                ' '.join([hex(b)[2:] for b in buffer[offset:offset + struct.calcsize(data_format)]]))
            )

    elif data_type is 'asciiArray':
        try:
            property_value = buffer[offset:offset + property_value_length].decode('ascii')
            offset += property_value_length
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_ASCII_ERROR.format(buffer[offset:offset + property_value_length])
            )

    elif data_type is 'byteArray':
        property_value = ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]])
        offset += property_value_length
    
    elif data_type is 'floatArray':
        try:

            property_value = struct.unpack('%sf' %int(property_value_length/4),buffer[offset:offset + property_value_length])
            offset += (property_value_length)

        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_FLOAT_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
        ###
            )
    elif data_type is 'doubleArray':
        try:

            property_value = struct.unpack('%sd' %int(property_value_length/8),buffer[offset:offset + property_value_length])
            offset += (property_value_length)
        ###
        except UnicodeDecodeError as _:
            raise m_common.DecoderException(
                DECODER_DOUBLE_ARRAY_ERROR.format(buffer[offset:offset + property_value_length])
        ###
            )

    else:  # 'invalid'
        property_value = '!' + ' '.join([hex(b)[2:] for b in buffer[offset:offset + property_value_length]]) + '!'
        offset += property_value_length

    json[property_name] = {'value': property_value, 'prefix': prefix, 'unit': unit}

    return offset
   
class Decoder:
    def __init__(self):
        self.declarations = {
            'node': {
                    5:{'unit': UNITS[0x10], 'type': 'floatArray', 'prefix': PREFIXES[0x0D], 'title': 'Shunt voltage', 'format': None},
                    6: {'unit': UNITS[0x10], 'type': 'floatArray', 'prefix': '', 'title': 'Bus voltage', 'format': None},
                    7: {'unit': UNITS[0x04], 'type': 'floatArray', 'prefix': PREFIXES[0x0D], 'title': 'Current', 'format': None},
                    8: {'unit': UNITS[0x0E], 'type': 'floatArray', 'prefix': PREFIXES[0x0D], 'title': 'Power', 'format': None},
                    9: {'unit': UNITS[0x03], 'type': 'doubleArray', 'prefix': '', 'title': 'Timestamp', 'format': None}
                    },
            'entity': {},
            'frame': {}
        }
        self.record_id = 0

    def reset(self):
        self.declarations['entity'] = {}
        self.declarations['frame'] = {}
        self.record_id = 0

    def node_add_decode(self, buffer, json):
        ((properties_count,), offset,) = block_decode("<B", buffer, 0)

        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset, self.declarations['node'])
        return json

    def node_property_add_decode(self, buffer, json):
        ((properties_count,), offset,) = block_decode("<B", buffer, 0)

        json['properties'] = {}
        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset, self.declarations['node'])
        return json

    def node_property_update_decode(self, buffer, json):
        ((properties_count,), offset,) = block_decode("<B", buffer, 0)

        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_reference_decode_node_update(buffer, json['properties'], offset, self.declarations['node'])
        return json

    def node_remove_decode(self, _, json):
        # there isn't much to decode ;)
        # yet we clear previous declarations as they're now obsolete
        self.declarations = {
            'node': {},
            'entity': {},
            'frame': {}
        }
        return json

    def entity_add_decode(self, buffer, json):
        decoded = block_decode("<BBB", buffer, 0)
        ((entity_id, entity_name_length, properties_count,), offset,) = decoded

        entity_name = buffer[offset:offset + entity_name_length].decode('ascii')
        offset += entity_name_length

        self.declarations['entity'][entity_id] = {'title': entity_name, 'links': {}, 'properties': {}}

        json['entityId'] = entity_name
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 self.declarations['entity'][entity_id]['properties'])
        return json

    def entity_property_add_decode(self, buffer, json):
        decoded = block_decode("<BB", buffer, 0)
        ((entity_id, properties_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 self.declarations['entity'][entity_id]['properties'])
        return json

    def entity_property_update_decode(self, buffer, json):
        decoded = block_decode("<BB", buffer, 0)
        ((entity_id, properties_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_reference_decode(buffer, json['properties'], offset,
                                               self.declarations['entity'][entity_id]['properties'])
        return json

    def entity_remove_decode(self, buffer, json):
        decoded = block_decode("<B", buffer, 0)
        ((entity_id,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['properties'] = {}

        del self.declarations['entity'][entity_id]

        return json

    def link_add_decode(self, buffer, json):
        decoded = block_decode("<BBBBB", buffer, 0)
        ((entity_id, link_id, src_prop_count, tgt_prop_count, link_prop_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        self.declarations['entity'][entity_id]['links'][link_id] = {
            'source_properties': {}, 'target_properties': {}, 'properties': {}
        }

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['linkId'] = link_id
        json['sourceProperties'] = {}
        json['targetProperties'] = {}
        json['properties'] = {}

        link_declarations = self.declarations['entity'][entity_id]['links'][link_id]

        for _ in repeat(None, src_prop_count):
            offset = property_reference_decode(buffer, json['sourceProperties'], offset,
                                               self.declarations['entity'][entity_id]['properties'])
        for _ in repeat(None, tgt_prop_count):
            offset = property_reference_decode(buffer, json['targetProperties'], offset,
                                               self.declarations['entity'][entity_id]['properties'])

        for _ in repeat(None, link_prop_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 link_declarations['properties'])

        return json

    def link_property_add_decode(self, buffer, json):
        decoded = block_decode("<BBB", buffer, 0)
        ((entity_id, link_id, link_prop_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if link_id not in self.declarations['entity'][entity_id]['links'].keys():
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_LINK_ID.format(link_id, self.declarations['entity'][entity_id]['title'])
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['linkId'] = link_id
        json['properties'] = {}

        link_declarations = self.declarations['entity'][entity_id]['links'][link_id]

        for _ in repeat(None, link_prop_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 link_declarations['properties'])

        return json

    def link_property_update_decode(self, buffer, json):
        decoded = block_decode("<BBB", buffer, 0)
        ((entity_id, link_id, link_prop_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if link_id not in self.declarations['entity'][entity_id]['links'].keys():
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_LINK_ID.format(link_id, self.declarations['entity'][entity_id]['title'])
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['linkId'] = link_id
        json['properties'] = {}

        link_declarations = self.declarations['entity'][entity_id]['links'][link_id]

        for _ in repeat(None, link_prop_count):
            offset = property_reference_decode(buffer, json['properties'], offset,
                                               link_declarations['properties'])

        return json

    def link_remove_decode(self, buffer, json):
        decoded = block_decode("<BB", buffer, 0)
        ((entity_id, link_id,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        del self.declarations['entity'][entity_id]['links'][link_id]

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['linkId'] = link_id
        json['properties'] = {}

    def frame_produce_decode(self, buffer, json):

        decoded = block_decode("<BBHB", buffer, 0)
        ((entity_id, frame_id, data_length, properties_count,), offset,) = decoded

        data = ' '.join([hex(b)[2:] for b in buffer[offset:offset + data_length]])
        offset += data_length

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        self.declarations['frame'][frame_id] = {}
        self.declarations['frame'][frame_id][entity_id] = {}

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['data'] = data
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 self.declarations['frame'][frame_id][entity_id])

        # hack for coverage study
        import requests
        location_status = requests.get('http://localhost:5555/location/status').json()
        json['properties']['latitude'] = {'value': location_status['latitude'], 'prefix': '', 'unit': ''}
        json['properties']['longitude'] = {'value': location_status['longitude'], 'prefix': '', 'unit': ''}
        return json

    def frame_property_add_decode(self, buffer, json):
        decoded = block_decode("<BBB", buffer, 0)
        ((entity_id, frame_id, properties_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if frame_id not in self.declarations['frame']:
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ID.format(frame_id, self.declarations['entity'][entity_id]['title'])
            )

        if entity_id not in self.declarations['frame'][frame_id]:
            self.declarations['frame'][frame_id][entity_id] = {}

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 self.declarations['frame'][frame_id][entity_id])

        return json

    def frame_property_update_decode(self, buffer, json):
        decoded = block_decode("<BBB", buffer, 0)
        ((entity_id, frame_id, properties_count,), offset,) = decoded

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if frame_id not in self.declarations['frame']:
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ID.format(frame_id, self.declarations['entity'][entity_id]['title'])
            )

        if frame_id not in self.declarations['frame'][entity_id]:
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ENTITY_ID.format(entity_id, frame_id)
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_reference_decode(buffer, json['properties'], offset,
                                               self.declarations['frame'][frame_id][entity_id])

        return json

    def frame_data_update_decode(self, buffer, json):
        decoded = block_decode("<BBH", buffer, 0)
        ((entity_id, frame_id, data_length), offset,) = decoded

        data = ' '.join([hex(b)[2:] for b in buffer[offset:offset + data_length]])
        offset += data_length

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if frame_id not in self.declarations['frame']:
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ID.format(frame_id, self.declarations['entity'][entity_id]['title'])
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['data'] = data
        json['properties'] = {}

        return json

    def frame_tx_decode(self, buffer, json):
        decoded = block_decode("<BBH", buffer, 0)
        ((entity_id, frame_id, data_length), offset,) = decoded

        data = ' '.join([hex(b)[2:] for b in buffer[offset:offset + data_length]])
        offset += data_length

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if frame_id not in self.declarations['frame']:
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ID.format(frame_id, self.declarations['entity'][entity_id]['title'])
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['data'] = data
        json['properties'] = {}

        return json

    def frame_rx_decode(self, buffer, json):
        decoded = block_decode("<BBHB", buffer, 0)
        ((entity_id, frame_id, data_length, properties_count,), offset,) = decoded

        data = ' '.join([hex(b)[2:] for b in buffer[offset:offset + data_length]])
        offset += data_length

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        self.declarations['frame'][frame_id] = {}
        self.declarations['frame'][frame_id][entity_id] = {}

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['data'] = data
        json['properties'] = {}

        for _ in repeat(None, properties_count):
            offset = property_declaration_decode(buffer, json['properties'], offset,
                                                 self.declarations['frame'][frame_id][entity_id])

        return json

    def frame_consume_decode(self, buffer, json):
        decoded = block_decode("<BBH", buffer, 0)
        ((entity_id, frame_id, data_length,), offset,) = decoded

        data = ' '.join([hex(b)[2:] for b in buffer[offset:offset + data_length]])
        offset += data_length

        if entity_id not in self.declarations['entity'].keys():
            # raise exception
            raise m_common.DecoderException(UNKNOWN_ENTITY_ID.format(entity_id))

        if frame_id not in self.declarations['frame']:
            # raise exception
            raise m_common.DecoderException(
                UNKNOWN_FRAME_ID.format(frame_id, self.declarations['entity'][entity_id]['title'])
            )

        json['entityId'] = self.declarations['entity'][entity_id]['title']
        json['frameId'] = frame_id
        json['data'] = data

        return json

    def decode(self, timestamp, buffer):
        decoded = block_decode("<IB", buffer)
        ((node_id, event_id), offset,) = decoded

        if event_id not in EVENTS.keys():
            raise m_common.DecoderException(
                UNKNOWN_EVENT_ID.format(event_id)
            )

        json = {
            'timestamp': timestamp,
            'nodeId': node_id,
            'eventId': EVENTS[event_id]['title'],
            'recordId': self.record_id
        }
        self.record_id += 1

        try:
            if EVENTS[event_id]['title'] == 'NodeAdd':
                self.node_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'NodePropertyAdd':
                self.node_property_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'NodePropertyUpdate':
                self.node_property_update_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'NodeRemove':
                self.node_remove_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'EntityAdd':
                self.entity_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'EntityPropertyAdd':
                self.entity_property_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'EntityPropertyUpdate':
                self.entity_property_update_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'EntityRemove':
                self.entity_remove_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'LinkAdd':
                self.link_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'LinkPropertyAdd':
                self.link_property_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'LinkPropertyUpdate':
                self.link_property_update_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'LinkRemove':
                self.link_remove_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FrameProduce':
                self.frame_produce_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FramePropertyAdd':
                self.frame_property_add_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FramePropertyUpdate':
                self.frame_property_update_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FrameDataUpdate':
                self.frame_data_update_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FrameTx':
                self.frame_tx_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FrameRx':
                self.frame_rx_decode(buffer[offset::], json)
            elif EVENTS[event_id]['title'] == 'FrameConsume':
                self.frame_consume_decode(buffer[offset::], json)
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            json['error'] = repr(traceback.format_exception(exc_type, exc_value, exc_traceback))
            print(e)
        return json
