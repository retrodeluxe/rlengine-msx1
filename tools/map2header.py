#!/usr/bin/env python
#
#   RetroDeLuxe Engine for MSX
#
#   Copyright (C) 2017 Enric Martin Geijo (retrodeluxemsx@gmail.com)
#
#   RDLEngine is free software: you can redistribute it and/or modify it under
#   the terms of the GNU General Public License as published by the Free
#   Software Foundation, version 2.
#
#   This program is distributed in the hope that it will be useful, but WITHOUT
#   ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#   FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
#   details.
#
#   You should have received a copy of the GNU General Public License along with
#   this program; If not, see <http://www.gnu.org/licenses/>.
#
import json
import sys
import os
import ntpath
from optparse import OptionParser

class MapObject:
    """
	Contains a Tiled Map object
	"""
    def __init__(self, raw):
        self.w = raw['width']
        self.h = raw['height']
        self.x = raw['x']
        self.y = raw['y']
        self.name = raw['name'].replace(' ','_')
        self.id = raw['id']
        self.visible = raw['visible']
        self.type = raw['type']
        self.rotation = raw['rotation']
        self.properties = {}
        if 'properties' in raw:
            self.properties = raw['properties'];

    def dump(self):
        print ("\tmapobject : [%s] [%s] [%s] (%s, %s)"  % \
            (self.id, self.name, self.type, self.x, self.y))

class TileLayer:
    """
	Contains a Tiled layer that contains tiles
	"""
    def __init__(self, raw, room_w, room_h):
        self.w = raw['width']
        self.h = raw['height']
        self.x = raw['x']
        self.y = raw['y']
        self.name = raw['name']
        self.opacity = raw['opacity']
        self.visible = raw['visible']
        self.data = raw['data']
        self.room_h = room_h
        self.room_w = room_w
        self.compress_all()

    def compress_all(self):
        # Compress RLE the whole map (cmpr ratio ~2)
        self.data_rle = self.compress_rle(self.data)

        # Split in rooms and compress each RLE (compr ratio ~2)
        self.data_rooms = self.room_split(self.data, self.room_w, self.room_h)
        self.data_rooms_rle = []
        for room in self.data_rooms:
            self.data_rooms_rle.append(self.compress_rle(room))

        # Compress the whole map using 4x4 blocks (compr ratio ~2 to 4)
        #   note: if the dictionary is bigger than 255 compression drops 50% because we need
        #   one additional byte to store each block
        self.block_dict = {}
        self.data_compr_4x4 = self.compress_4x4_dict(self.data, self.w, self.h)
        self.data_compr_4x4_dict = self.block_dict

        # Split in rooms and compress each using 4x4 blocks
        #   in most cases this is the most efficient compression, with compr ratio of ~4
        #   regardless of the size of the whole map.
        self.data_rooms_compr_4x4 = []
        self.data_rooms_compr_4x4_dict = []
        for block in self.data_rooms:
            self.block_dict = {}
            self.data_rooms_compr_4x4.append(self.compress_4x4_dict(block, self.room_w, self.room_h))
            self.data_rooms_compr_4x4_dict.append(self.block_dict)

    def room_split(self, buf_in, w, h):
        buf_out = []
        for bx in range(0, self.w/w):
            for by in range(0, self.h/h):
                offset = bx * w + by * h * self.w
                block = []
                for y in range(0, h):
                    for x in range(0, w):
                        block.append(buf_in[offset + x + y * self.w])
                buf_out.append(block)
        return buf_out

    def compress_rle(self, bufin):
        cnt = 0
        size = len(bufin)
        bufout = []
        while cnt < size:
            idx = cnt
            val = bufin[idx]
            idx+=1
            while idx < size and idx - cnt < 255 and bufin[idx] == val:
                idx+=1
            if idx - cnt == 1:
                while idx < size and idx - cnt < 255 and  \
                    (bufin[idx] != bufin[idx-1] or idx > 1 \
                        and bufin[idx] != bufin[idx-2]):
                    idx+=1
                while idx < size and bufin[idx] == bufin[idx-1]:
                    idx-=1
                bufout.append(cnt - idx)
                for i in range(cnt,idx):
                    bufout.append(bufin[i])
            else:
                bufout.append(idx - cnt)
                bufout.append(val)
            cnt=idx
        return bufout

    def lookup_4x4_dict(self, block):
        key = str(block[0]) + '_' + str(block[1]) + '_' + str(block[2]) + '_' + str(block[3])
        if self.block_dict.has_key(key):
            return self.block_dict[key]
        else:
            new_idx = len(self.block_dict) + 1
            self.block_dict[key] = new_idx
            return new_idx

    def compress_4x4_dict(self, buf, w, h):
        bufout = []
        for i in range(0, h, 2):
            for j in range(0, w, 2):
                block = [buf[i * w + j],buf[i * w + j + 1], \
                    buf[(i + 1) * w + j],buf[(i + 1) * w + j +1]]
                bufout.append(self.lookup_4x4_dict(block) - 1) # need to adjust to zero
        return bufout

    def expand_block_keys(self, dict_data):
        lo = []
        for idx in range(0,len(dict_data) + 1):
            for key in dict_data.keys():
                if dict_data[key] == idx:
                    vals = key.rsplit('_')
                    a = int(vals[0])
                    b = int(vals[1])
                    c = int(vals[2])
                    d = int(vals[3])
                    lo.extend([a,b,c,d])
        return lo

    def dump(self):
        print ("tilelayer [%s] : uncompressed [%s] rle [%d]" % \
           (self.name, len(self.data), len(self.data_rle)))

    def dump_as_c_header_accessor(self, mode, file):
        """
        Provide accessor for map segments (only makes sense in modes 3 and 4)
        """
        if mode == 3:
            print ("FATAL: not implemented")
            exit(1)
        elif mode ==4:
            print >>file,("unsigned char *map_segment_dict[%s];" % len(self.data_rooms_compr_4x4_dict))
            print >>file,("unsigned char *map_segment[%s];" % len(self.data_rooms_compr_4x4))
            print >>file,("void init_map_segments(void) {")
            room_cnt = 0
            for room_dict in self.data_rooms_compr_4x4_dict:
                print >>file,("\tmap_segment_dict[%s] = segment%s_%s_dict;" % (room_cnt,room_cnt, self.name))
                room_cnt+=1
            room_cnt = 0
            for room_data in self.data_rooms_compr_4x4:
                print >>file,("\tmap_segment[%s] = segment_%s_%s;" % (room_cnt, room_cnt, self.name))
                room_cnt+=1
            print >>file,("};")
        else:
            pass
        pass

    def dump_as_c_header_no_data(self, mode, file):
        print >>file,("extern const unsigned char %s_w;" % (self.name))
        print >>file,("extern const unsigned char %s_h;" % (self.name))
        if mode == 1:
            # RLE
            print >>file,("extern const unsigned int %s_rle[];" % self.name)
        elif mode == 2:
            # 4x4 Blocks
            print >>file,("extern const unsigned int %s_cmpr_size;" % (self.name))
            print >>file,("extern const unsigned char %s_cmpr_dict[];" % self.name)
            print >>file,("extern const unsigned int %s[];" % self.name)
        elif mode == 3:
            room_cnt = 0
            for room_data in self.data_rooms_rle:
                print >>file,("extern const unsigned int segment%s_%s_rle[];" % (room_cnt, self.name))
                room_cnt+=1
        elif mode == 4:
            room_cnt = 0
            for room_dict in self.data_rooms_compr_4x4_dict:
                print >>file,("extern const unsigned char segment%s_%s_dict[];" % (room_cnt, self.name))
                room_cnt+=1
            room_cnt = 0
            for room_data in self.data_rooms_compr_4x4:
                print >>file,("extern const unsigned char segment%s_%s[];" % (room_cnt, self.name))
                room_cnt+=1
        else:
            print >>file,("extern const unsigned char %s[];" % self.name)

    def dump_as_c_header(self, mode, file):
        """ Dump contents of tile layer as a C header.
            mode indicates compression:
            0 : uncompressed
            1 : rle
            2 : 4x4 block compression
            3 : split in rooms and compressed rle
            4 : split in rooms and compress using 4x4 blocks
        """
        total_size = 0
        print >>file,("const unsigned char %s_w = %s;" % (self.name, self.w))
        print >>file,("const unsigned char %s_h = %s;" % (self.name, self.h))
        if mode == 1:
            # RLE
            print >>file,("const unsigned int %s_rle[] = {" % self.name)
            total_size += len(self.data_rle)
            for tile in self.data_rle:
                print >>file,("%s," % tile),
            print >>file,"0 };"
        elif mode == 2:
            # 4x4 Blocks
            print >>file,("const unsigned int %s_cmpr_size = %s;" % (self.name, len(self.data_compr_4x4)))
            print >>file,("const unsigned char %s_cmpr_dict[] = {" % self.name),
            total_size += len(self.expand_block_keys(self.data_compr_4x4_dict))
            for tile in self.expand_block_keys(self.data_compr_4x4_dict):
                print >>file,("%s," % tile ),
            print >>file,"0 };"
            print >>file,("const unsigned int %s[] = {" % self.name),
            total_size += len(self.data_compr_4x4) * 2
            for tile in self.data_compr_4x4:
                print >>file,("%s," % tile ),
            print >>file,"0 };"
        elif mode == 3:
            room_cnt = 0
            for room_data in self.data_rooms_rle:
                print >>file,("const unsigned int segment%s_%s_rle[] = {" % (room_cnt, self.name))
                total_size += len(room_data)
                for tile in room_data:
                    print >>file,("%s," % tile),
                print >>file,"0 };"
                room_cnt+=1
        elif mode == 4:
            room_cnt = 0
            for room_dict in self.data_rooms_compr_4x4_dict:
                print >>file,("const unsigned char segment%s_%s_dict[] = {" % (room_cnt, self.name)),
                total_size += len(self.expand_block_keys(room_dict))
                for tile in self.expand_block_keys(room_dict):
                    print >>file,("%s," % tile ),
                print >>file,"0 };"
                room_cnt+=1
            room_cnt = 0
            for room_data in self.data_rooms_compr_4x4:
                print >>file,("const unsigned char segment%s_%s[] = {" % (room_cnt, self.name)),
                total_size += len(room_data)
                for tile in room_data:
                    print >>file,("%s," % tile ),
                print >>file,"0 };"
                room_cnt+=1
        else:
            # uncompressed output (should not be allowed?)
            print >>file,("const unsigned char %s[] = {" % self.name)
            total_size += len(self.data)
            for tile in self.data:
                val = (tile % 256)
                print >>file,("%s," % val),
            print >>file,"0 };"
        print >>file,("// TOTAL_SIZE %s" % total_size)
        return total_size

class ObjectGroupLayer:
    """ Contains an object group layer
	"""
    def __init__(self, raw):
        self.w = raw['width']
        self.h = raw['height']
        self.x = raw['x']
        self.y = raw['y']
        self.name = raw['name'].replace(' ','_')
        self.opacity = raw['opacity']
        self.visible = raw['visible']
        self.draworder = raw['draworder']
        self.raw_objects = raw['objects']
        self.objects = []
        for obj in self.raw_objects:
            self.objects.append(MapObject(obj))
        self.extract_properties() # we run this globa

    def extract_properties(self):
        """
        Extract properties just for this Object Layer
        """
        self.object_properties = {}
        self.enum_properties = {}
        self.max_num_properties = 1;
        for item in self.raw_objects:
            # find all types or names
            _type = item['type']
            if _type == '':
                _type = item['name']
            if 'properties' in item:
                # Add properties to dict avoiding repetitions.
                if _type in self.object_properties:
                    already_added = set(self.object_properties[_type])
                    new_items = set(item['properties'].keys())
                    to_be_added = new_items - already_added
                    self.object_properties[_type] = self.object_properties[_type] + list(to_be_added)
                else:
                    self.object_properties[_type] = item['properties'].keys()
                length = len(item['properties'].keys())
                if length > self.max_num_properties:
                    self.max_num_properties = length
                ## Find Properties that require enums
                for _property in item['properties'].keys():
                    value = item['properties'][_property]
                    if (not value.isdigit() and not value.replace('.','').isdigit()):
                        if not _property in self.enum_properties:
                            self.enum_properties[_property] = {}
                        self.enum_properties[_property][value.encode('ascii','ignore')] = '1'

    def dump(self):
        print ("object group : [%s] (%s, %s)" % (self.name, self.x, self.y))
        for obj in self.objects:
            obj.dump()

    def dump_as_c_header_no_data(self, file):
        count = 0
        for item in self.raw_objects:
            print >>file,("const unsigned char %s_obj%s[];\n" % (self.name, count)),
            count = count + 1

    def dump_as_c_header(self, file):
        count = 0
        total_size = 0
        for item in self.raw_objects:
            print >>file,("const unsigned char %s_obj%s[] = {" % (self.name, count)),
            _type = item['type']
            if _type == '':
                _type = item['name']
            # type is like MOVABLE, coordinates should be able to be negative up to -32
            print >>file,("%s, %s, %s, %s, %s, %s," % (_type.upper(),  \
                item['x'] % 256,  item['y'] % 176,  item['width'],  \
                item['height'], 1 if item['visible'] else 0)),
            total_size += 6
            for _property in self.object_properties[_type]:
                if 'properties' in item and _property in item['properties']:
                    value = item['properties'][_property]
                else:
                    value = "0"
                if _property in self.enum_properties and not value.isdigit():
                    ## this is like TYPE_TEMPLAR
                    print >>file,("%s_%s," % (_property.upper(), value.upper())),
                elif not value.isdigit() and value.replace('.','').isdigit:
                    print >>file,("%s," % (value.replace('.',''))),
                elif value.isdigit():
                    wrap = int(value) % 256
                    ## regular numeric value, wrapped to byte
                    print >>file,("%s," % wrap),
                else:
                    print >>file,("%s," % value),
            total_size += len(self.object_properties[_type])
            print >>file,("};")
            count = count + 1
        return total_size

    def dump_structures(self):
        """ Dump data structures and definitions
            to interpret the data from C code.
        """
        if len(self.object_properties.keys()) > 0:
			print "\nenum object_type {"
			for key in self.object_properties.keys():
				print ("    %s, " % key.upper())
			print ("};\n")

			## enum_properties
			for key in self.enum_properties:
				print ("\nenum object_property_%s {" % key.encode('ascii', 'ignore'))
				for _property in self.enum_properties[key]:
					print ("    %s_%s, " % (key.encode('ascii', 'ignore').upper(), _property.upper()))
				print ("};\n")

    def dump_initializer(self):
        """ Generate initialization code
        """
        pass

class TiledMap:
        """ Contains Tiled Map Data """
        def __init__(self, raw_map):
            self.map_version = raw_map['version']
            self.map_orientation = raw_map['orientation']
            self.tile_w = raw_map['tilewidth']
            self.tile_h = raw_map['tileheight']
            self.map_w = raw_map['width']
            self.map_h = raw_map['height']
            self.raw_layers = raw_map['layers']
            if 'room_width' in raw_map['properties']:
                self.room_w = raw_map['properties']['room_width']
            if 'room_heigth' in raw_map['properties']:
                self.room_h = raw_map['properties']['room_heigth']
            self.tile_layers = []
            self.objectgroup_layers = []
            self.process_layers()

        def __setitem__(self,key,value):
            self.__dict__[key]=value

        def __getitem__(self,key):
            return self.__dict__[key]

        def process_layers(self):
            for layer in self.raw_layers:
                if 'tilelayer' in layer['type']:
                    self.tile_layers.append(TileLayer(layer, self.room_w, self.room_h))
                elif 'objectgroup' in layer['type']:
                    self.objectgroup_layers.append(ObjectGroupLayer(layer))

class TileMapWriter:
        """ writes a tile map to set of C header files
        """
        def __init__(self, tilemap, output, rle, block, split):
            self.tilemap = tilemap
            self.rle = rle
            self.block = block
            self.split = split
            self.output = output
            self.block_dict = {}

        def extract_properties(self):
            """
            Extract properties from all object layers
            """
            self.object_properties = {}
            self.enum_properties = {}
            self.max_num_properties = 1;
            for object_layer in self.tilemap.objectgroup_layers:
                for item in object_layer.raw_objects:
                    # find all types or names
                    _type = item['type']
                    if _type == '':
                        _type = item['name']
                    if 'properties' in item:
                        # Add properties to dict avoiding repetitions.
                        if _type in self.object_properties:
                            already_added = set(self.object_properties[_type])
                            new_items = set(item['properties'].keys())
                            to_be_added = new_items - already_added
                            self.object_properties[_type] = self.object_properties[_type] + list(to_be_added)
                        else:
                            self.object_properties[_type] = item['properties'].keys()
                        length = len(item['properties'].keys())
                        if length > self.max_num_properties:
                            self.max_num_properties = length
                        ## Find Properties that require enums
                        for _property in item['properties'].keys():
                            value = item['properties'][_property]
                            if (not value.isdigit() and not value.replace('.','').isdigit()):
                                if not _property in self.enum_properties:
                                    self.enum_properties[_property] = {}
                                self.enum_properties[_property][value.encode('ascii','ignore')] = '1'

        def generate_headers(self):
            self.extract_properties()
            self.write_definitions()
            self.write_tilelayers()
            self.write_objectgroup_layers()

        def write_definitions(self):
            """
            Write header file containing typedefs and structs
            """
            filename, file_extension = os.path.splitext(self.output)
            basepath= ntpath.basename(self.output)
            basename, base_extension = os.path.splitext(basepath)

            fout = open(filename + '_defs.h', 'w+')
            basename = basename + '_defs'

            print >>fout,("#ifndef __MAP_DATA_%s_H" % basename.upper())
            print >>fout,("#define __MAP_DATA_%s_H" % basename.upper())

            if len(self.object_properties.keys()) > 0:
    			print >>fout, "\nenum object_type {"
    			for key in self.object_properties.keys():
    				print >>fout, ("    %s, " % key.upper())
    			print >>fout,("};\n")

    			## enum_properties
    			for key in self.enum_properties:
    				print >>fout,("\nenum object_property_%s {" % key.encode('ascii', 'ignore'))
    				for _property in self.enum_properties[key]:
    					print >>fout,("    %s_%s, " % (key.encode('ascii', 'ignore').upper(), _property.upper()))
    				print >>fout,("};\n")

            ## now additional structures and unions...
            for key in self.object_properties.keys():
                ## here keys and properties cannot be C keywords
                print >>fout,("struct map_object_%s {" % key)
                if len(self.object_properties[key]) > 0:
                    for _property in self.object_properties[key]:
                        ## TODO filter C Keywords
                        if _property == 'static':
                            _property = 'static_'
                        if _property in self.enum_properties:
                            print >>fout,("     enum object_property_%s %s;" % (_property, _property))
                        else:
                            print >>fout,("     unsigned char %s;" % _property)
                else:
                    print >>fout,("     unsigned char dummy;")
                print >>fout,("};\n")

            if len(self.object_properties.keys()) > 0:
                print >>fout,("union map_object {")
                for key in self.object_properties.keys():
                    if key == "static":
                        _key = "static_"
                    else:
                        _key = key
                    print >>fout,("    struct map_object_%s %s;" % (key, _key))
                print >>fout,("};")

            print >>fout,"struct map_object_item {"
            print >>fout,("    enum object_type type;")
            print >>fout,("    unsigned char x;")
            print >>fout,("    unsigned char y;")
            print >>fout,("    unsigned char w;")
            print >>fout,("    unsigned char h;")
            print >>fout,("    unsigned char visible;")
            if len(self.object_properties.keys()) > 0:
                print >>fout,("    union map_object object;")
            print >>fout,"};\n"

            ## Accessor structures and initialization function for the map
            #
            for layer in self.tilemap.tile_layers:
                layer.dump_as_c_header_accessor(4, fout)

            #
            # This (and other code initializations must be in a separate file...)
            #
            print >>fout,("unsigned char *map_object_index[%s];" % len(self.tilemap.objectgroup_layers))
            print >>fout,("void init_map_objects() {")
            count = 0
            for layer in self.tilemap.objectgroup_layers:
                name = layer.name.replace(' ','_')
                print >>fout,( "\tmap_object_index[%s] = %s; " % (count, name))
                count = count + 1
            print >>fout,("}")
            print >>fout,"#endif"

        def write_tilelayers(self):
            """
            Write header file containing typedefs and structs
            """
            filename, file_extension = os.path.splitext(self.output)
            basepath= ntpath.basename(self.output)
            basename, base_extension = os.path.splitext(basepath)

            ## Fist write data
            ##
            for layer in self.tilemap.tile_layers:
                fout = open(filename + '_layer_'+ layer.name +'.h', 'w+')
                basename = basename + '_layer_'+ layer.name

                print >>fout,("#ifndef __MAP_DATA_%s_H" % basename.upper())
                print >>fout,("#define __MAP_DATA_%s_H" % basename.upper())

                size = layer.dump_as_c_header(4, fout)
                if size > 8192:
                    print ("FATAL: map file bigger than 8k")
                    exit(1)
                print >>fout,"#endif"

            ## Next write ext files
            ##
            for layer in self.tilemap.tile_layers:
                fout = open(filename + '_layer_'+ layer.name +'_ext.h', 'w+')

                print >>fout,("#ifndef __MAP_DATA_%s_EXT_H" % basename.upper())
                print >>fout,("#define __MAP_DATA_%s_EXT_H" % basename.upper())

                layer.dump_as_c_header_no_data(4, fout)

                print >>fout,"#endif"

        def write_objectgroup_layers(self):
            """
            Write all object layers in a single output file
            """
            filename, file_extension = os.path.splitext(self.output)
            basepath= ntpath.basename(self.output)
            basename, base_extension = os.path.splitext(basepath)

            ## First write data
            #
            fout = open(filename + '_layer_objects.h', 'w+')
            basename = basename + '_layer_objects'

            print >>fout,("#ifndef __MAP_DATA_%s_H" % basename.upper())
            print >>fout,("#define __MAP_DATA_%s_H" % basename.upper())

            size = 0
            for layer in self.tilemap.objectgroup_layers:
                size += layer.dump_as_c_header(fout)
            if size > 8192:
                print ("FATAL: map file bigger than 8k")
                exit(1)

            print >>fout,"#endif"

            ## Next write ext files
            #
            fout = open(filename + '_layer_objects_ext.h', 'w+')

            print >>fout,("#ifndef __MAP_DATA_%s_EXT_H" % basename.upper())
            print >>fout,("#define __MAP_DATA_%s_EXT_H" % basename.upper())

            for layer in self.tilemap.objectgroup_layers:
                layer.dump_as_c_header_no_data(fout)
            print >>fout,"#endif"

class TiledMapJsonReader:
        """ reads a json file saved from tiled"""
        def __init__(self, filename):
            self.filename = filename;

        def read(self):
            self.data = open(self.filename)
            self.decoded = json.load(self.data)
            return TiledMap(self.decoded)

if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option("-s", "--source", dest="source", action="store", default=None,
                        help="Source json file containing the tilemap")
    parser.add_option("-o", "--output", dest="output", action="store", default=None,
                        help="Basename of output header files containing the data")
    parser.add_option("-r", "--rle", dest="rle", action="store_true",
                       default=False, help="Compress tilemap data using RLE")
    parser.add_option("-b", "--block", dest="block", action="store_true",
                       default=False, help="Compress tilemap data using 4x4 block replacement dictionary")
    parser.add_option("-x", "--split", dest="split", action="store",
                       default=None, help="Split map into rectangles of AxB tiles each")

    (opts, args) = parser.parse_args()
    if not opts.source:
        print "required source"
        sys.exit(1)

    reader = TiledMapJsonReader(opts.source)
    writer = TileMapWriter(reader.read(), opts.output, opts.rle, opts.block, opts.split)

    writer.generate_headers()
