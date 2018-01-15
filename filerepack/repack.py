#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys, os ,random

from os.path import isfile, join, exists, abspath
from shutil import move, rmtree
from os import listdir, walk
import uuid
import logging
import tempfile
from .consts import *

TEMP_PATH = tempfile.gettempdir()


def pack_jpg(filepath, debug=False):
    """Lossy compress JPG file using jpegoptim"""
    insize = os.path.getsize(filepath)
    cmd = JPEGOPTIM_PATH + JPEGIOPTIM_OPTIONS + '"' + filepath + '"'
    if debug:
        logging.info('jpeg optimization cmd: %s' % (cmd))
    os.system(cmd)
    outsize = os.path.getsize(filepath)
    if insize > 0:
        share = (insize - outsize) * 100.0 / insize
    else:
        share = 0
    return [filepath, insize, outsize, share]

def pack_png(filepath, debug=False):
    """Lossless compress png files using pngquant"""
    insize = os.path.getsize(filepath)
    from shutil import copyfile
    tempname = uuid.uuid4().hex + '.png'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    copyfile(filepath, tempfpath)
    mediapath = filepath.rsplit('/', 1)[0]
    cmd = PNGQUANT_PATH + PNGQUANT_OPTIONS + '"' + tempfpath + '"'
    if debug:
        logging.info('png optimization cmd: %s' % (cmd))
    os.system(cmd)
    new_filename = tempname.rsplit('.', 1)[0] + '-fs8.png'
    if os.path.exists(abspath(os.path.join(TEMP_PATH, new_filename))):
        move(os.path.join(TEMP_PATH, new_filename), abspath(filepath))
        os.remove(tempfpath)
    outsize = os.path.getsize(filepath)
    if insize > 0:
        share = (insize - outsize) * 100.0 / insize
    else:
        share = 0
    return [filepath, insize, outsize, share]



class FileRepacker:
    """Document repacker class"""
    def __init__(self, quiet=False, temppath=None):
        self.quiet = quiet
        random.seed()
        self.toolpath = SZIP_PATH
        self.temppath = temppath if temppath else TEMP_PATH
        self.currpath = os.getcwd()

    def pack_images(self, mediapath, recursive=False, options={'debug' : False}):
        """Packs all images"""
        results = {'stats' : [0, 0, 0], 'files' : []}
        if not exists(mediapath):
            return None
        if not recursive:
            onlyfiles = [ f for f in listdir(mediapath) if isfile(join(mediapath, f)) ]
            for f in onlyfiles:
                res = None
                ext = f.rsplit('.', 1)[-1].lower()
                fn = join(mediapath, f)
                if ext in ['jpg', 'jpeg']:
                    res = pack_jpg(fn, debug=options['debug'])
                elif ext  == 'png':
                    res = pack_png(fn, debug=options['debug'])
                    if res is not None:
                        results['files'].append([fn, res[1], res[2], res[3]])
                        outfile, insize, outsize, share = res
                        results['stats'][0] += 1
                        results['stats'][1] += insize
                        results['stats'][2] += outsize
        else:
            for root, dirs, files in walk(mediapath):
                for f in files:
                    res = None
                    ext = f.rsplit('.', 1)[-1].lower()
                    fn = join(root, f)
                    if ext in ['jpg', 'jpeg']:
                        res = pack_jpg(fn, debug=options['debug'])
                    elif ext  == 'png':
                        res = pack_png(fn, debug=options['debug'])
                    if res is not None:
                        results['files'].append([fn, res[1], res[2], res[3]])
                        outfile, insize, outsize, share = res
                        results['stats'][0] += 1
                        results['stats'][1] += insize
                        results['stats'][2] += outsize
        return results


    def repack_zip_file(self, filename, outfile=None,
                        options={"debug": False, 'pack_images': True, 'repack_archive': True, 'pack_archives': True,
                                 'deep_walking': True, 'log': False, 'quiet': False}):
        """Repack single ZIP file """
        results = {'stats': [0, 0, 0], 'files': []}
        f_outfile = outfile
        if outfile is None: f_outfile = filename
        f_insize = os.path.getsize(filename)
        filetype = filename.rsplit('.', 1)[-1].lower()
        rnd = random.randint(1, 1000)
        tempname = uuid.uuid4().hex
        if filetype in SUPPORTED_EXTS:
            fpath = os.path.join(self.temppath, tempname)  # os.path.basename(filename) + '_' + str(rnd)
            os.mkdir(fpath)
            fn = SZIP_PATH + ' x -o%s "%s"' % (fpath, filename)
            if options['debug']:
                logging.debug('Filename %s' % fn)
            os.system(fn)
            if options['debug']:
                self.log('Filetype %s' % str(filetype))
            rpath = os.path.abspath(filename)
            # Deep walking. Looking into every directory and every file
            if options['deep_walking']:
                for root, dirs, files in os.walk(fpath):
                    for name in files:
                        ext = name.rsplit('.', 1)[-1].lower()
                        fullname = os.path.join(root, name)
                        res = None
                        if ext in SUPPORTED_EXTS:
                            if options['pack_archives']:
                                res = self.repack_zip_file(fullname, fullname, options)
                                if res is not None:
                                    results['files'].append([fullname, res['final'][0], res['final'][1], res['final'][2]])
                                    results['stats'][0] += 1
                                    results['stats'][1] += res['stats'][1]
                                    results['stats'][2] += res['stats'][2]
                        else:
                            if ext in ['jpg', 'jpeg']:
                                if options['pack_images']:
                                    res = pack_jpg(fullname, options)
                            elif ext in ['png', ]:
                                if options['pack_images']:
                                    res = pack_png(fullname, options)
                            if res is not None:
                                results['files'].append([name, res[1], res[2], res[3]])
                                outfile, insize, outsize, share = res
                                results['stats'][0] += 1
                                results['stats'][1] += insize
                                results['stats'][2] += outsize
            else:
                # if not deep walking we use only preset of directories
                mediapaths = []
                for mp in EXT_IMAGE_MAP[filetype]:
                    mediapaths.append(fpath + mp)
                    for mp in mediapaths:
                        if options['pack_images']:
                            res = self.pack_images(mp, True, options)
                            if res is not None:
#                                results['files'].append([fn, res['stats'][1], res['stats'][2],
#                                                        (res['stats'][1] - res['stats'][2]) * 100.0 / res['stats'][
#                                                           1] if res['stats'][1] > 0 else 0])
                                results['stats'][0] += 1
                                results['stats'][1] += res['stats'][1]
                                results['stats'][2] += res['stats'][2]

            if filetype in ZIP_SENSITIVE_EXTS:
                fn = ZIP_PATH + ' -r -q -9 "%s" *' % (rpath,)
            else:
                fn = self.toolpath + ' -tzip -mx9 a "%s" *' % (rpath,)
#            fn = fn + " 1>/dev/null 2>/dev/null"
            if not options['debug']:
                fn = fn  # + ' > /dev/null'
            # Execute zip shrinking cmd
            os.chdir(fpath)
            os.system(fn)
            os.chdir(self.currpath)
            rmtree(fpath)
            # Calc size gains
            outsize = os.path.getsize(f_outfile)
            share = (f_insize - outsize) * 100.0 / f_insize if f_insize > 0 else 0
            if not options['quiet']:
                logging.debug('File %s shrinked %d -> %d (%f%%)' % (f_outfile.encode('utf8'), f_insize, outsize, share))
            results['final'] = [f_insize, outsize, share]
            return results

if __name__ == "__main__":
	dr = FileRepacker()
	results = dr.repack_zip_file(sys.argv[1])

