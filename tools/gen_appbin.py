#!/usr/bin/python
#
# File	: gen_appbin.py
# This file is part of Espressif's generate bin script.
# Copyright (C) 2013 - 2015, Espressif Systems

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


"""This file is part of Espressif's generate bin script.
    argv[1] is elf file name
    argv[2] is version num"""

import string
import sys
import os
import re
import binascii
import struct


TEXT_ADDRESS = 0x40100000
# app_entry = 0
# data_address = 0x3ffb0000
# data_end  = 0x40000000
# text_end  = 0x40120000

CHECKSUM_INIT = 0xEF

chk_sum = CHECKSUM_INIT
blocks = 0

def write_file(file_name,data):
	if file_name is None:
		print 'file_name cannot be none\n'
		sys.exit(0)

	fp = open(file_name,'ab')

	if fp:
		fp.seek(0,os.SEEK_END)
		fp.write(data)
		fp.close()
	else:
		print '%s write fail\n'%(file_name)

def combine_bin(file_name,dest_file_name,start_offset_addr,need_chk):
    global chk_sum
    global blocks
    if dest_file_name is None:
        print 'dest_file_name cannot be none\n'
        sys.exit(0)

    if file_name:
        fp = open(file_name,'rb')
        if fp:
        	########## write text ##########
            fp.seek(0,os.SEEK_END)
            data_len = fp.tell()
            if data_len:
		if need_chk:
                    tmp_len = (data_len + 3) & (~3)
		else:
	            tmp_len = (data_len + 15) & (~15)
                data_bin = struct.pack('<II',start_offset_addr,tmp_len)
                write_file(dest_file_name,data_bin)
                fp.seek(0,os.SEEK_SET)
                data_bin = fp.read(data_len)
                write_file(dest_file_name,data_bin)
		if need_chk:
		    for loop in range(len(data_bin)):
		        chk_sum ^= ord(data_bin[loop])
                # print '%s size is %d(0x%x),align 4 bytes,\nultimate size is %d(0x%x)'%(file_name,data_len,data_len,tmp_len,tmp_len)
                tmp_len = tmp_len - data_len
                if tmp_len:
                    data_str = ['00']*(tmp_len)
                    data_bin = binascii.a2b_hex(''.join(data_str))
                    write_file(dest_file_name,data_bin)
		    if need_chk:
			for loop in range(len(data_bin)):
			    chk_sum ^= ord(data_bin[loop])
                blocks = blocks + 1
        	fp.close()
        else:
        	print '!!!Open %s fail!!!'%(file_name)

def gen_appbin():
    global chk_sum
    global blocks
    if len(sys.argv) != 6:
        print 'Usage: gen_appbin.py eagle.app.out boot_mode flash_mode flash_clk_div flash_size'
        sys.exit(0)

    elf_file = sys.argv[1]
    boot_mode = sys.argv[2]
    flash_mode = sys.argv[3]
    flash_clk_div = sys.argv[4]
    flash_size = sys.argv[5]

    flash_data_line  = 16
    data_line_bits = 0xf

    irom0text_bin_name = 'eagle.app.v6.irom0text.bin'
    text_bin_name = 'eagle.app.v6.text.bin'
    data_bin_name = 'eagle.app.v6.data.bin'
    rodata_bin_name = 'eagle.app.v6.rodata.bin'
    flash_bin_name ='eagle.app.flash.bin'

    BIN_MAGIC_FLASH  = 0xE9
    BIN_MAGIC_IROM   = 0xEA
    data_str = ''
    sum_size = 0

    if os.getenv('COMPILE')=='gcc' :
        cmd = 'xtensa-lx106-elf-nm -g ' + elf_file + ' > eagle.app.sym'
    else :
        cmd = 'xt-nm -g ' + elf_file + ' > eagle.app.sym'

    os.system(cmd)

    fp = file('./eagle.app.sym')
    if fp is None:
        print "open sym file error\n"
        sys.exit(0)

    lines = fp.readlines()
    fp.close()

    entry_addr = None
    p = re.compile('(\w*)(\sT\s)(call_user_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            entry_addr = m.group(1)
            # print entry_addr

    if entry_addr is None:
        print 'no entry point!!'
        sys.exit(0)

    data_start_addr = '0'
    p = re.compile('(\w*)(\sA\s)(_data_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            data_start_addr = m.group(1)
            # print data_start_addr

    rodata_start_addr = '0'
    p = re.compile('(\w*)(\sA\s)(_rodata_start)$')
    for line in lines:
        m = p.search(line)
        if m != None:
            rodata_start_addr = m.group(1)
            # print rodata_start_addr

    # write flash bin header
    #============================
    #  SPI FLASH PARAMS
    #-------------------
    #flash_mode=
    #     0: QIO
    #     1: QOUT
    #     2: DIO
    #     3: DOUT
    #-------------------
    #flash_clk_div=
    #     0 :  80m / 2
    #     1 :  80m / 3
    #     2 :  80m / 4
    #    0xf:  80m / 1
    #-------------------
    #flash_size=
    #     0 : 512 KB
    #     1 : 256 KB
    #     2 : 1024 KB
    #     3 : 2048 KB
    #     4 : 4096 KB
    #-------------------
    #   END OF SPI FLASH PARAMS
    #============================
    byte2=int(flash_mode)&0xff
    byte3=(((int(flash_size)<<4)| int(flash_clk_div))&0xff)
	
    if boot_mode == '2':
        # write irom bin head
        data_bin = struct.pack('<BBBBI',BIN_MAGIC_IROM,4,byte2,byte3,long(entry_addr,16))
        sum_size = len(data_bin)
        write_file(flash_bin_name,data_bin)
        
        # irom0.text.bin
        combine_bin(irom0text_bin_name,flash_bin_name,0x0,0)

    data_bin = struct.pack('<BBBBI',BIN_MAGIC_FLASH,3,byte2,byte3,long(entry_addr,16))
    sum_size = len(data_bin)
    write_file(flash_bin_name,data_bin)

    # text.bin
    combine_bin(text_bin_name,flash_bin_name,TEXT_ADDRESS,1)

    # data.bin
    if data_start_addr:
        combine_bin(data_bin_name,flash_bin_name,long(data_start_addr,16),1)

    # rodata.bin
    combine_bin(rodata_bin_name,flash_bin_name,long(rodata_start_addr,16),1)

    # write checksum header
    sum_size = os.path.getsize(flash_bin_name) + 1
    sum_size = flash_data_line - (data_line_bits&sum_size)
    if sum_size:
        data_str = ['00']*(sum_size)
        data_bin = binascii.a2b_hex(''.join(data_str))
        write_file(flash_bin_name,data_bin)
    write_file(flash_bin_name,chr(chk_sum & 0xFF))
    	
    if boot_mode == '1':
        sum_size = os.path.getsize(flash_bin_name)
        data_str = ['FF']*(0x10000-sum_size)
        data_bin = binascii.a2b_hex(''.join(data_str))
        write_file(flash_bin_name,data_bin)

        fp = open(irom0text_bin_name,'rb')
        if fp:
            data_bin = fp.read()
            write_file(flash_bin_name,data_bin)
            fp.close()
        else :
            print '!!!Open %s fail!!!'%(flash_bin_name)
            sys.exit(0)

    cmd = 'rm eagle.app.sym'
    os.system(cmd)

if __name__=='__main__':
    gen_appbin()
