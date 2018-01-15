#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys, os ,random

from os.path import isfile, join, exists, abspath
from shutil import move, rmtree
from os import listdir, walk
import uuid
import logging
from filerepack import FileRepacker


def run(filename):
    dr = FileRepacker()
    results = dr.repack_zip_file(filename)
    print('File %s shrinked %d -> %d (%f%%)' % (filename.encode('utf8'), results['final'][0], results['final'][1], results['final'][2]))
    if len(results['files']) > 0:
        print('Files recompressed:')
        for fdata in results['files']:
            print('- %s: %d -> %d (%f%%)' % (fdata[0], fdata[1], fdata[2], fdata[3]))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print('Usage: frepacker.py [filename]')
