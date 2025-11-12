#!/usr/bin/env python
#-*- coding: utf-8 -*-

import sys, os ,random

from os.path import isfile, join, exists, abspath
from shutil import move, rmtree, which
from os import listdir, walk
import uuid
import logging
import tempfile
import gzip
import lzma
import bz2
from .consts import *
try:
    import duckdb
except ImportError:
    logging.warning('duckdb not installed, will not be able to compress parquet files') 
    duckdb = None

TEMP_PATH = tempfile.gettempdir()

def pack_parquet(filepath, debug=False, quiet=False, ultra=False):
    """Lossless compress parquet file using duckdb"""
    if duckdb is None:
        logging.warning('duckdb not installed, will not be able to compress parquet files')
        return None
    insize = os.path.getsize(filepath)
    c_level = 22 if ultra else 19
    tempname = uuid.uuid4().hex + '.parquet'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    try:
        # Use absolute path for duckdb command
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        # Escape single quotes in file paths for duckdb SQL command
        escaped_filepath = abs_filepath.replace("'", "''")
        escaped_tempfpath = abs_tempfpath.replace("'", "''")
        # Construct duckdb command with proper quoting
        sql_cmd = f"COPY (SELECT * FROM read_parquet('{escaped_filepath}')) TO '{escaped_tempfpath}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL {c_level})"
        cmd = f'duckdb -c "{sql_cmd}"'
        if quiet:
            if os.name == 'nt':  # Windows
                cmd = cmd + ' > nul 2>&1'
            else:  # Unix-like
                cmd = cmd + ' > /dev/null 2>&1'
        if debug:
            logging.info('parquet compression cmd: %s' % (cmd))
        os.system(cmd)
        if os.path.exists(tempfpath):
            temp_file_created = True
            move(tempfpath, abs_filepath)
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('parquet compression failed, output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('parquet compression failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup   

def pack_gzip(filepath, debug=False, quiet=False):
    """Repack Gzip file with maximum compression (level 9). Uses pigz if available, otherwise uses Python gzip."""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.gz'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    decompressed_temp = None
    
    # Check if pigz is available
    pigz_path = which('pigz')
    
    try:
        # Decompress the original file
        with gzip.open(filepath, 'rb') as f_in:
            decompressed_data = f_in.read()
        
        if pigz_path:
            # Use pigz for compression (parallel gzip, often faster and better compression)
            decompressed_temp = os.path.join(TEMP_PATH, uuid.uuid4().hex)
            with open(decompressed_temp, 'wb') as f_out:
                f_out.write(decompressed_data)
            
            # Compress with pigz at maximum compression level (9)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{pigz_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{pigz_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>/dev/null'
            else:
                cmd = f'{pigz_path} -9 -c "{decompressed_temp}" > "{tempfpath}"'
            if debug:
                logging.info('pigz compression cmd: %s' % (cmd))
            os.system(cmd)
        else:
            # Fall back to Python's gzip module
            with gzip.open(tempfpath, 'wb', compresslevel=9) as f_out:
                f_out.write(decompressed_data)
        
        # Clean up decompressed temp file if it was created
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        
        if os.path.exists(tempfpath):
            move(tempfpath, abspath(filepath))
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            tool_used = 'pigz' if pigz_path else 'gzip'
            if debug:
                logging.info('gzip repack (%s): %s %d -> %d (%f%%)' % (tool_used, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('gzip repack failed, output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('gzip repack failed: %s' % str(e))
        # Clean up temp files if they exist
        if os.path.exists(tempfpath):
            os.remove(tempfpath)
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        return None

def pack_xz(filepath, debug=False, quiet=False):
    """Repack XZ file with maximum compression (level 9). Uses xz command if available, otherwise uses Python lzma."""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.xz'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    decompressed_temp = None
    
    # Check if xz command is available
    xz_path = which('xz')
    
    try:
        # Decompress the original file
        with lzma.open(filepath, 'rb') as f_in:
            decompressed_data = f_in.read()
        
        if xz_path:
            # Use xz command for compression (often better compression)
            decompressed_temp = os.path.join(TEMP_PATH, uuid.uuid4().hex)
            with open(decompressed_temp, 'wb') as f_out:
                f_out.write(decompressed_data)
            
            # Compress with xz at maximum compression level (9)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{xz_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{xz_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>/dev/null'
            else:
                cmd = f'{xz_path} -9 -c "{decompressed_temp}" > "{tempfpath}"'
            if debug:
                logging.info('xz compression cmd: %s' % (cmd))
            os.system(cmd)
        else:
            # Fall back to Python's lzma module
            with lzma.open(tempfpath, 'wb', preset=9) as f_out:
                f_out.write(decompressed_data)
        
        # Clean up decompressed temp file if it was created
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        
        if os.path.exists(tempfpath):
            move(tempfpath, abspath(filepath))
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            tool_used = 'xz' if xz_path else 'lzma'
            if debug:
                logging.info('xz repack (%s): %s %d -> %d (%f%%)' % (tool_used, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('xz repack failed, output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('xz repack failed: %s' % str(e))
        # Clean up temp files if they exist
        if os.path.exists(tempfpath):
            os.remove(tempfpath)
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        return None

def pack_bz2(filepath, debug=False, quiet=False):
    """Repack BZ2 file with maximum compression (level 9). Uses bzip2 command if available, otherwise uses Python bz2."""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.bz2'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    decompressed_temp = None
    
    # Check if bzip2 command is available
    bzip2_path = which('bzip2')
    
    try:
        # Decompress the original file
        with bz2.open(filepath, 'rb') as f_in:
            decompressed_data = f_in.read()
        
        if bzip2_path:
            # Use bzip2 command for compression (often better compression)
            decompressed_temp = os.path.join(TEMP_PATH, uuid.uuid4().hex)
            with open(decompressed_temp, 'wb') as f_out:
                f_out.write(decompressed_data)
            
            # Compress with bzip2 at maximum compression level (9)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{bzip2_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{bzip2_path} -9 -c "{decompressed_temp}" > "{tempfpath}" 2>/dev/null'
            else:
                cmd = f'{bzip2_path} -9 -c "{decompressed_temp}" > "{tempfpath}"'
            if debug:
                logging.info('bzip2 compression cmd: %s' % (cmd))
            os.system(cmd)
        else:
            # Fall back to Python's bz2 module
            with bz2.open(tempfpath, 'wb', compresslevel=9) as f_out:
                f_out.write(decompressed_data)
        
        # Clean up decompressed temp file if it was created
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        
        if os.path.exists(tempfpath):
            move(tempfpath, abspath(filepath))
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            tool_used = 'bzip2' if bzip2_path else 'bz2'
            if debug:
                logging.info('bz2 repack (%s): %s %d -> %d (%f%%)' % (tool_used, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('bz2 repack failed, output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('bz2 repack failed: %s' % str(e))
        # Clean up temp files if they exist
        if os.path.exists(tempfpath):
            os.remove(tempfpath)
        if decompressed_temp and os.path.exists(decompressed_temp):
            os.remove(decompressed_temp)
        return None

def pack_pdf(filepath, debug=False, quiet=False):
    """Lossless compress PDF file using ghostscript (with qpdf as fallback)"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.pdf'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ghostscript is available (primary tool)
    gs_path = which('gs')
    if gs_path is None:
        # Try alternative names
        gs_path = which('gswin64c') or which('gswin32c')
    
    # Check if qpdf is available (fallback tool)
    qpdf_path = which('qpdf')
    
    if gs_path is None and qpdf_path is None:
        if debug:
            logging.warning('Neither ghostscript nor qpdf is installed, will not be able to compress PDF files')
        return None
    
    try:
        # Try ghostscript first (better compression)
        if gs_path:
            try:
                # Use absolute paths for ghostscript command
                abs_filepath = abspath(filepath).replace('\\', '/')
                abs_tempfpath = abspath(tempfpath).replace('\\', '/')
                
                # ghostscript command for lossless compression:
                # -sDEVICE=pdfwrite: output PDF format
                # -dCompatibilityLevel=1.4: PDF 1.4 compatibility
                # -dPDFSETTINGS=/prepress: high quality settings (lossless)
                # -dNOPAUSE -dQUIET -dBATCH: non-interactive mode
                # -dColorImageResolution=300 -dGrayImageResolution=300: preserve image quality
                # -dAutoRotatePages=/None: preserve page orientation
                # -sOutputFile: output file
                if quiet:
                    if os.name == 'nt':  # Windows
                        cmd = f'{gs_path} -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -dColorImageResolution=300 -dGrayImageResolution=300 -dAutoRotatePages=/None -sOutputFile="{abs_tempfpath}" "{abs_filepath}" 2>nul'
                    else:  # Unix-like
                        cmd = f'{gs_path} -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -dColorImageResolution=300 -dGrayImageResolution=300 -dAutoRotatePages=/None -sOutputFile="{abs_tempfpath}" "{abs_filepath}" 2>/dev/null'
                else:
                    cmd = f'{gs_path} -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/prepress -dNOPAUSE -dQUIET -dBATCH -dColorImageResolution=300 -dGrayImageResolution=300 -dAutoRotatePages=/None -sOutputFile="{abs_tempfpath}" "{abs_filepath}"'
                if debug:
                    logging.info('ghostscript compression cmd: %s' % (cmd))
                
                result = os.system(cmd)
                
                # Check if ghostscript command succeeded (exit code 0)
                if result == 0 and os.path.exists(tempfpath) and os.path.getsize(tempfpath) > 0:
                    temp_file_created = True
                    move(tempfpath, abs_filepath)
                    outsize = os.path.getsize(filepath)
                    if insize > 0:
                        share = (insize - outsize) * 100.0 / insize
                    else:
                        share = 0
                    if debug:
                        logging.info('pdf repack (ghostscript): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
                    return [filepath, insize, outsize, share]
                else:
                    if debug:
                        logging.warning('ghostscript compression failed, trying qpdf fallback')
            except Exception as e:
                if debug:
                    logging.warning('ghostscript compression failed: %s, trying qpdf fallback' % str(e))
        
        # Fallback to qpdf if ghostscript failed or is not available
        if not temp_file_created and qpdf_path:
            try:
                # Use absolute paths for qpdf command
                abs_filepath = abspath(filepath).replace('\\', '/')
                abs_tempfpath = abspath(tempfpath).replace('\\', '/')
                
                # qpdf command: qpdf --linearize --object-streams=preserve input.pdf output.pdf
                # --linearize: optimize for web viewing and reduce file size
                # --object-streams=preserve: preserve object streams for better compression
                # --suppress-password-recovery: suppress password recovery warnings (non-interactive)
                if quiet:
                    if os.name == 'nt':  # Windows
                        cmd = f'{qpdf_path} --linearize --object-streams=preserve --suppress-password-recovery "{abs_filepath}" "{abs_tempfpath}" 2>nul'
                    else:  # Unix-like
                        cmd = f'{qpdf_path} --linearize --object-streams=preserve --suppress-password-recovery "{abs_filepath}" "{abs_tempfpath}" 2>/dev/null'
                else:
                    cmd = f'{qpdf_path} --linearize --object-streams=preserve --suppress-password-recovery "{abs_filepath}" "{abs_tempfpath}"'
                if debug:
                    logging.info('qpdf compression cmd (fallback): %s' % (cmd))
                
                result = os.system(cmd)
                
                # Check if qpdf command succeeded (exit code 0)
                if result == 0 and os.path.exists(tempfpath):
                    temp_file_created = True
                    move(tempfpath, abs_filepath)
                    outsize = os.path.getsize(filepath)
                    if insize > 0:
                        share = (insize - outsize) * 100.0 / insize
                    else:
                        share = 0
                    if debug:
                        logging.info('pdf repack (qpdf fallback): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
                    return [filepath, insize, outsize, share]
                else:
                    if debug:
                        logging.warning('pdf repack failed, both ghostscript and qpdf commands returned non-zero exit code or output file not found')
                    return None
            except Exception as e:
                if debug:
                    logging.warning('pdf repack failed: %s' % str(e))
                return None
        else:
            if debug:
                logging.warning('pdf repack failed, ghostscript failed and qpdf is not available')
            return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_gif(filepath, debug=False, quiet=False):
    """Lossless compress GIF file using gifsicle"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.gif'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if gifsicle is available
    gifsicle_path = which('gifsicle')
    if gifsicle_path is None:
        if debug:
            logging.warning('gifsicle not installed, will not be able to compress GIF files')
        return None
    
    try:
        # Use absolute paths for gifsicle command
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        # gifsicle command: gifsicle -O3 --lossy=0 input.gif -o output.gif
        # -O3: maximum optimization level
        # --lossy=0: lossless compression (no quality loss)
        # --batch: process files without prompting (non-interactive)
        if quiet:
            if os.name == 'nt':  # Windows
                cmd = f'{gifsicle_path} -O3 --lossy=0 --batch "{abs_filepath}" -o "{abs_tempfpath}" 2>nul'
            else:  # Unix-like
                cmd = f'{gifsicle_path} -O3 --lossy=0 --batch "{abs_filepath}" -o "{abs_tempfpath}" 2>/dev/null'
        else:
            cmd = f'{gifsicle_path} -O3 --lossy=0 --batch "{abs_filepath}" -o "{abs_tempfpath}"'
        if debug:
            logging.info('gifsicle compression cmd: %s' % (cmd))
        
        result = os.system(cmd)
        
        # Check if gifsicle command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            move(tempfpath, abs_filepath)
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('gif repack (gifsicle): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('gif repack failed, gifsicle command returned non-zero exit code or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('gif repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_webp(filepath, debug=False, quiet=False):
    """Lossless compress WebP file using dwebp and cwebp"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.webp'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_png = os.path.join(TEMP_PATH, uuid.uuid4().hex + '.png')
    temp_file_created = False
    
    # Check if dwebp and cwebp are available
    dwebp_path = which('dwebp')
    cwebp_path = which('cwebp')
    
    if dwebp_path is None or cwebp_path is None:
        if debug:
            logging.warning('dwebp or cwebp not installed, will not be able to compress WebP files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        abs_temp_png = abspath(temp_png).replace('\\', '/')
        
        # Step 1: Decode WebP to PNG using dwebp
        # dwebp is non-interactive by default
        if quiet:
            if os.name == 'nt':  # Windows
                decode_cmd = f'{dwebp_path} "{abs_filepath}" -o "{abs_temp_png}" 2>nul'
            else:  # Unix-like
                decode_cmd = f'{dwebp_path} "{abs_filepath}" -o "{abs_temp_png}" 2>/dev/null'
        else:
            decode_cmd = f'{dwebp_path} "{abs_filepath}" -o "{abs_temp_png}"'
        
        if debug:
            logging.info('dwebp decode cmd: %s' % (decode_cmd))
        
        decode_result = os.system(decode_cmd)
        
        if decode_result != 0 or not os.path.exists(temp_png):
            if debug:
                logging.warning('webp repack failed, dwebp decode failed')
            return None
        
        # Step 2: Re-encode PNG to WebP with lossless compression using cwebp
        # -lossless: use lossless compression
        # -z 9: maximum compression level (0-9)
        # cwebp is non-interactive by default
        if quiet:
            if os.name == 'nt':  # Windows
                encode_cmd = f'{cwebp_path} -lossless -z 9 "{abs_temp_png}" -o "{abs_tempfpath}" 2>nul'
            else:  # Unix-like
                encode_cmd = f'{cwebp_path} -lossless -z 9 "{abs_temp_png}" -o "{abs_tempfpath}" 2>/dev/null'
        else:
            encode_cmd = f'{cwebp_path} -lossless -z 9 "{abs_temp_png}" -o "{abs_tempfpath}"'
        
        if debug:
            logging.info('cwebp encode cmd: %s' % (encode_cmd))
        
        encode_result = os.system(encode_cmd)
        
        # Check if cwebp command succeeded (exit code 0)
        if encode_result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            move(tempfpath, abs_filepath)
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('webp repack (dwebp+cwebp): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('webp repack failed, cwebp encode failed or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('webp repack failed: %s' % str(e))
        return None
    finally:
        # Ensure all temp files are cleaned up
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup
        if os.path.exists(temp_png):
            try:
                os.remove(temp_png)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_svg(filepath, debug=False, quiet=False):
    """Lossless compress SVG file using svgo (or scour as fallback)"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.svg'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if svgo is available (preferred)
    svgo_path = which('svgo')
    # Check if scour is available (fallback)
    scour_path = which('scour') if svgo_path is None else None
    
    if svgo_path is None and scour_path is None:
        if debug:
            logging.warning('svgo or scour not installed, will not be able to compress SVG files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        if svgo_path:
            # svgo command: svgo --input input.svg --output output.svg
            # svgo automatically optimizes SVG files losslessly
            # svgo is non-interactive by default
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{svgo_path} --input "{abs_filepath}" --output "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{svgo_path} --input "{abs_filepath}" --output "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{svgo_path} --input "{abs_filepath}" --output "{abs_tempfpath}"'
            tool_used = 'svgo'
        else:
            # scour command: scour --enable-viewboxing --enable-id-stripping --enable-comment-stripping --remove-metadata --strip-xml-prolog --no-line-breaks input.svg output.svg
            # scour optimizes SVG files losslessly
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{scour_path} --enable-viewboxing --enable-id-stripping --enable-comment-stripping --remove-metadata --strip-xml-prolog --no-line-breaks "{abs_filepath}" "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{scour_path} --enable-viewboxing --enable-id-stripping --enable-comment-stripping --remove-metadata --strip-xml-prolog --no-line-breaks "{abs_filepath}" "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{scour_path} --enable-viewboxing --enable-id-stripping --enable-comment-stripping --remove-metadata --strip-xml-prolog --no-line-breaks "{abs_filepath}" "{abs_tempfpath}"'
            tool_used = 'scour'
        
        if debug:
            logging.info('svg compression cmd (%s): %s' % (tool_used, cmd))
        
        result = os.system(cmd)
        
        # Check if command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            move(tempfpath, abs_filepath)
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('svg repack (%s): %s %d -> %d (%f%%)' % (tool_used, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('svg repack failed, %s command returned non-zero exit code or output file not found' % tool_used)
            return None
    except Exception as e:
        if debug:
            logging.warning('svg repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_wmv(filepath, debug=False, quiet=False, lossless=False):
    """Compress WMV file using ffmpeg with lossless or lossy compression
    
    Note: Output will be converted to MP4 container with H.264 codec for better compatibility.
    The original WMV file will be replaced with the compressed MP4 file.
    """
    insize = os.path.getsize(filepath)
    # Use .mp4 extension for output (standard container for H.264)
    tempname = uuid.uuid4().hex + '.mp4'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ffmpeg is available
    ffmpeg_path = which('ffmpeg')
    if ffmpeg_path is None:
        if debug:
            logging.warning('ffmpeg not installed, will not be able to compress WMV files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        if lossless:
            # Lossless compression: use libx264 with crf 0 (lossless)
            # -c:v libx264: use H.264 codec
            # -crf 0: lossless mode (constant rate factor 0 = lossless)
            # -preset veryslow: best compression (slowest)
            # -c:a copy: copy audio stream without re-encoding (if compatible)
            # -movflags +faststart: optimize for streaming
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossless'
        else:
            # Lossy compression: use libx264 with crf 18 (high quality)
            # -c:v libx264: use H.264 codec
            # -crf 18: high quality (lower = better quality, 18 is visually lossless for most content)
            # -preset slow: good balance between compression and speed
            # -c:a copy: copy audio stream without re-encoding (if compatible)
            # -movflags +faststart: optimize for streaming
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossy'
        
        if debug:
            logging.info('ffmpeg wmv compression cmd (%s): %s' % (mode, cmd))
        
        result = os.system(cmd)
        
        # Check if ffmpeg command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            # Replace original WMV file with compressed MP4 file
            # Output is MP4 since WMV container doesn't support H.264 well
            original_ext = filepath.rsplit('.', 1)[-1].lower()
            if original_ext == 'wmv':
                # Change extension to .mp4
                new_filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            else:
                new_filepath = filepath
            
            # Remove original file and move compressed file
            if os.path.exists(filepath):
                os.remove(filepath)
            move(tempfpath, abspath(new_filepath))
            filepath = new_filepath
            
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('wmv repack (ffmpeg, %s): %s %d -> %d (%f%%)' % (mode, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('wmv repack failed, ffmpeg command returned non-zero exit code or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('wmv repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_mp4(filepath, debug=False, quiet=False, lossless=False):
    """Compress MP4 file using ffmpeg with lossless or lossy compression"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.mp4'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ffmpeg is available
    ffmpeg_path = which('ffmpeg')
    if ffmpeg_path is None:
        if debug:
            logging.warning('ffmpeg not installed, will not be able to compress MP4 files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        if lossless:
            # Lossless compression: use libx264 with crf 0 (lossless)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossless'
        else:
            # Lossy compression: use libx264 with crf 18 (high quality)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossy'
        
        if debug:
            logging.info('ffmpeg mp4 compression cmd (%s): %s' % (mode, cmd))
        
        result = os.system(cmd)
        
        # Check if ffmpeg command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            # Replace original file with compressed version
            if os.path.exists(filepath):
                os.remove(filepath)
            move(tempfpath, abs_filepath)
            
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('mp4 repack (ffmpeg, %s): %s %d -> %d (%f%%)' % (mode, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('mp4 repack failed, ffmpeg command returned non-zero exit code or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('mp4 repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_avi(filepath, debug=False, quiet=False, lossless=False):
    """Compress AVI file using ffmpeg with lossless or lossy compression
    
    Note: Output will be converted to MP4 container with H.264 codec for better compatibility.
    The original AVI file will be replaced with the compressed MP4 file.
    """
    insize = os.path.getsize(filepath)
    # Use .mp4 extension for output (standard container for H.264)
    tempname = uuid.uuid4().hex + '.mp4'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ffmpeg is available
    ffmpeg_path = which('ffmpeg')
    if ffmpeg_path is None:
        if debug:
            logging.warning('ffmpeg not installed, will not be able to compress AVI files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        if lossless:
            # Lossless compression: use libx264 with crf 0 (lossless)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossless'
        else:
            # Lossy compression: use libx264 with crf 18 (high quality)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossy'
        
        if debug:
            logging.info('ffmpeg avi compression cmd (%s): %s' % (mode, cmd))
        
        result = os.system(cmd)
        
        # Check if ffmpeg command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            # Replace original AVI file with compressed MP4 file
            original_ext = filepath.rsplit('.', 1)[-1].lower()
            if original_ext == 'avi':
                # Change extension to .mp4
                new_filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            else:
                new_filepath = filepath
            
            # Remove original file and move compressed file
            if os.path.exists(filepath):
                os.remove(filepath)
            move(tempfpath, abspath(new_filepath))
            filepath = new_filepath
            
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('avi repack (ffmpeg, %s): %s %d -> %d (%f%%)' % (mode, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('avi repack failed, ffmpeg command returned non-zero exit code or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('avi repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_asf(filepath, debug=False, quiet=False, lossless=False):
    """Compress ASF file using ffmpeg with lossless or lossy compression
    
    Note: Output will be converted to MP4 container with H.264 codec for better compatibility.
    The original ASF file will be replaced with the compressed MP4 file.
    """
    insize = os.path.getsize(filepath)
    # Use .mp4 extension for output (standard container for H.264)
    tempname = uuid.uuid4().hex + '.mp4'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ffmpeg is available
    ffmpeg_path = which('ffmpeg')
    if ffmpeg_path is None:
        if debug:
            logging.warning('ffmpeg not installed, will not be able to compress ASF files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        if lossless:
            # Lossless compression: use libx264 with crf 0 (lossless)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 0 -preset veryslow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossless'
        else:
            # Lossy compression: use libx264 with crf 18 (high quality)
            if quiet:
                if os.name == 'nt':  # Windows
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>nul'
                else:  # Unix-like
                    cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}" 2>/dev/null'
            else:
                cmd = f'{ffmpeg_path} -i "{abs_filepath}" -c:v libx264 -crf 18 -preset slow -c:a copy -movflags +faststart -y "{abs_tempfpath}"'
            mode = 'lossy'
        
        if debug:
            logging.info('ffmpeg asf compression cmd (%s): %s' % (mode, cmd))
        
        result = os.system(cmd)
        
        # Check if ffmpeg command succeeded (exit code 0)
        if result == 0 and os.path.exists(tempfpath):
            temp_file_created = True
            # Replace original ASF file with compressed MP4 file
            original_ext = filepath.rsplit('.', 1)[-1].lower()
            if original_ext == 'asf':
                # Change extension to .mp4
                new_filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            else:
                new_filepath = filepath
            
            # Remove original file and move compressed file
            if os.path.exists(filepath):
                os.remove(filepath)
            move(tempfpath, abspath(new_filepath))
            filepath = new_filepath
            
            outsize = os.path.getsize(filepath)
            if insize > 0:
                share = (insize - outsize) * 100.0 / insize
            else:
                share = 0
            if debug:
                logging.info('asf repack (ffmpeg, %s): %s %d -> %d (%f%%)' % (mode, filepath, insize, outsize, share))
            return [filepath, insize, outsize, share]
        else:
            if debug:
                logging.warning('asf repack failed, ffmpeg command returned non-zero exit code or output file not found')
            return None
    except Exception as e:
        if debug:
            logging.warning('asf repack failed: %s' % str(e))
        return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

def pack_jpg_re(filepath, debug=False, quiet=False):
    """Lossy compress JPG file using jpeg-recompress"""
    insize = os.path.getsize(filepath)
    cmd = JPEG_RE_CMD + ' ' + JPEG_RE_OPTIONS + ' "' + filepath + '"' + ' "' + filepath + '"' 
    if quiet:
        cmd = cmd + ' > /dev/null 2>&1'
    if debug:
        logging.info('jpeg recompress cmd: %s' % (cmd))
    os.system(cmd)
    outsize = os.path.getsize(filepath)
    if insize > 0:
        share = (insize - outsize) * 100.0 / insize
    else:
        share = 0
    return [filepath, insize, outsize, share]


def pack_jpg_re(filepath, debug=False, quiet=False):
    """Lossy compress JPG file using jpeg-recompress"""
    insize = os.path.getsize(filepath)
    cmd = JPEG_RE_CMD + ' ' + JPEG_RE_OPTIONS + ' "' + filepath + '"' + ' "' + filepath + '"' 
    if quiet:
        cmd = cmd + ' > /dev/null 2>&1'
    if debug:
        logging.info('jpeg recompress cmd: %s' % (cmd))
    os.system(cmd)
    outsize = os.path.getsize(filepath)
    if insize > 0:
        share = (insize - outsize) * 100.0 / insize
    else:
        share = 0
    return [filepath, insize, outsize, share]


def pack_jpg(filepath, debug=False, quiet=False, jpeg_quality=None):
    """Lossy compress JPG file using jpegoptim"""
    insize = os.path.getsize(filepath)
    # Use custom quality if provided, otherwise use default
    if jpeg_quality is not None:
        jpeg_options = ' --strip-all -m%s -p -o -f ' % (str(jpeg_quality))
    else:
        jpeg_options = JPEGIOPTIM_OPTIONS
    cmd = JPEGOPTIM_PATH + jpeg_options + '"' + filepath + '"'
    if quiet:
        if os.name == 'nt':  # Windows
            cmd = cmd + ' > nul 2>&1'
        else:  # Unix-like
            cmd = cmd + ' > /dev/null 2>&1'
    if debug:
        logging.info('jpeg optimization cmd: %s' % (cmd))
    os.system(cmd)
    outsize = os.path.getsize(filepath)
    if insize > 0:
        share = (insize - outsize) * 100.0 / insize
    else:
        share = 0
    return [filepath, insize, outsize, share]

def pack_png(filepath, debug=False, quiet=False, png_quality=None):
    """Lossless compress png files using pngquant"""
    insize = os.path.getsize(filepath)
    from shutil import copyfile
    tempname = uuid.uuid4().hex + '.png'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    copyfile(filepath, tempfpath)
    mediapath = filepath.rsplit('/', 1)[0]
    # pngquant quality: high=1, medium=2, low=3 (speed setting)
    if png_quality == 'high':
        png_options = ' --force --speed 1 '
    elif png_quality == 'medium':
        png_options = ' --force --speed 2 '
    elif png_quality == 'low':
        png_options = ' --force --speed 3 '
    else:
        png_options = PNGQUANT_OPTIONS
    cmd = PNGQUANT_PATH + png_options + '"' + tempfpath + '"'
    if quiet:
        if os.name == 'nt':  # Windows
            cmd = cmd + ' > nul 2>&1'
        else:  # Unix-like
            cmd = cmd + ' > /dev/null 2>&1'
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

def pack_tif(filepath, debug=False, quiet=False):
    """Lossless compress TIF/TIFF file using ImageMagick (with tiffcp as fallback)"""
    insize = os.path.getsize(filepath)
    tempname = uuid.uuid4().hex + '.tif'
    tempfpath = os.path.join(TEMP_PATH, tempname)
    temp_file_created = False
    
    # Check if ImageMagick is available (primary tool)
    convert_path = which('convert')
    if convert_path is None:
        # Try alternative names
        convert_path = which('magick')
    
    # Check if tiffcp is available (fallback tool)
    tiffcp_path = which('tiffcp')
    
    if convert_path is None and tiffcp_path is None:
        if debug:
            logging.warning('Neither ImageMagick (convert) nor tiffcp is installed, will not be able to compress TIF files')
        return None
    
    try:
        # Use absolute paths
        abs_filepath = abspath(filepath).replace('\\', '/')
        abs_tempfpath = abspath(tempfpath).replace('\\', '/')
        
        # Try ImageMagick first (better compression and more features)
        if convert_path:
            try:
                # ImageMagick command for lossless compression:
                # -compress lzw: use LZW compression (lossless, good compression)
                # -strip: remove metadata to reduce file size
                # -quiet: suppress warnings (non-interactive)
                if quiet:
                    if os.name == 'nt':  # Windows
                        cmd = f'{convert_path} "{abs_filepath}" -compress lzw -strip -quiet "{abs_tempfpath}" 2>nul'
                    else:  # Unix-like
                        cmd = f'{convert_path} "{abs_filepath}" -compress lzw -strip -quiet "{abs_tempfpath}" 2>/dev/null'
                else:
                    cmd = f'{convert_path} "{abs_filepath}" -compress lzw -strip -quiet "{abs_tempfpath}"'
                if debug:
                    logging.info('ImageMagick TIF compression cmd: %s' % (cmd))
                
                result = os.system(cmd)
                
                # Check if ImageMagick command succeeded (exit code 0)
                if result == 0 and os.path.exists(tempfpath) and os.path.getsize(tempfpath) > 0:
                    temp_file_created = True
                    move(tempfpath, abs_filepath)
                    outsize = os.path.getsize(filepath)
                    if insize > 0:
                        share = (insize - outsize) * 100.0 / insize
                    else:
                        share = 0
                    if debug:
                        logging.info('tif repack (ImageMagick): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
                    return [filepath, insize, outsize, share]
                else:
                    if debug:
                        logging.warning('ImageMagick TIF compression failed, trying tiffcp fallback')
            except Exception as e:
                if debug:
                    logging.warning('ImageMagick TIF compression failed: %s, trying tiffcp fallback' % str(e))
        
        # Fallback to tiffcp if ImageMagick failed or is not available
        if not temp_file_created and tiffcp_path:
            try:
                # tiffcp command for lossless compression:
                # -c lzw: use LZW compression (lossless)
                # -r: remove metadata tags
                if quiet:
                    if os.name == 'nt':  # Windows
                        cmd = f'{tiffcp_path} -c lzw -r "{abs_filepath}" "{abs_tempfpath}" 2>nul'
                    else:  # Unix-like
                        cmd = f'{tiffcp_path} -c lzw -r "{abs_filepath}" "{abs_tempfpath}" 2>/dev/null'
                else:
                    cmd = f'{tiffcp_path} -c lzw -r "{abs_filepath}" "{abs_tempfpath}"'
                if debug:
                    logging.info('tiffcp TIF compression cmd (fallback): %s' % (cmd))
                
                result = os.system(cmd)
                
                # Check if tiffcp command succeeded (exit code 0)
                if result == 0 and os.path.exists(tempfpath):
                    temp_file_created = True
                    move(tempfpath, abs_filepath)
                    outsize = os.path.getsize(filepath)
                    if insize > 0:
                        share = (insize - outsize) * 100.0 / insize
                    else:
                        share = 0
                    if debug:
                        logging.info('tif repack (tiffcp fallback): %s %d -> %d (%f%%)' % (filepath, insize, outsize, share))
                    return [filepath, insize, outsize, share]
                else:
                    if debug:
                        logging.warning('tif repack failed, both ImageMagick and tiffcp commands returned non-zero exit code or output file not found')
                    return None
            except Exception as e:
                if debug:
                    logging.warning('tif repack failed: %s' % str(e))
                return None
        else:
            if debug:
                logging.warning('tif repack failed, ImageMagick failed and tiffcp is not available')
            return None
    finally:
        # Ensure temp file is cleaned up if it still exists
        if not temp_file_created and os.path.exists(tempfpath):
            try:
                os.remove(tempfpath)
            except Exception:
                pass  # Ignore errors during cleanup

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
        quiet = options.get('quiet', False)
        if not exists(mediapath):
            return None
        if not recursive:
            onlyfiles = [ f for f in listdir(mediapath) if isfile(join(mediapath, f)) ]
            for f in onlyfiles:
                res = None
                ext = f.rsplit('.', 1)[-1].lower()
                fn = join(mediapath, f)
                if ext in ['jpg', 'jpeg']:
                    res = pack_jpg(fn, debug=options['debug'], quiet=quiet, jpeg_quality=options.get('jpeg_quality'))
                elif ext  == 'png':
                    res = pack_png(fn, debug=options['debug'], quiet=quiet, png_quality=options.get('png_quality'))
                elif ext == 'gif':
                    res = pack_gif(fn, debug=options['debug'], quiet=quiet)
                elif ext == 'webp':
                    res = pack_webp(fn, debug=options['debug'], quiet=quiet)
                elif ext == 'svg':
                    res = pack_svg(fn, debug=options['debug'], quiet=quiet)
                elif ext in ['tif', 'tiff']:
                    res = pack_tif(fn, debug=options['debug'], quiet=quiet)
                elif ext == 'wmv':
                    wmv_lossless = options.get('wmv_lossless', False)
                    res = pack_wmv(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                elif ext == 'mp4':
                    wmv_lossless = options.get('wmv_lossless', False)
                    res = pack_mp4(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                elif ext == 'avi':
                    wmv_lossless = options.get('wmv_lossless', False)
                    res = pack_avi(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                elif ext == 'asf':
                    wmv_lossless = options.get('wmv_lossless', False)
                    res = pack_asf(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
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
                        res = pack_jpg(fn, debug=options['debug'], quiet=quiet, jpeg_quality=options.get('jpeg_quality'))
                    elif ext  == 'png':
                        res = pack_png(fn, debug=options['debug'], quiet=quiet, png_quality=options.get('png_quality'))
                    elif ext == 'gif':
                        res = pack_gif(fn, debug=options['debug'], quiet=quiet)
                    elif ext == 'webp':
                        res = pack_webp(fn, debug=options['debug'], quiet=quiet)
                    elif ext == 'svg':
                        res = pack_svg(fn, debug=options['debug'], quiet=quiet)
                    elif ext in ['tif', 'tiff']:
                        res = pack_tif(fn, debug=options['debug'], quiet=quiet)
                    elif ext == 'wmv':
                        wmv_lossless = options.get('wmv_lossless', False)
                        res = pack_wmv(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                    elif ext == 'mp4':
                        wmv_lossless = options.get('wmv_lossless', False)
                        res = pack_mp4(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                    elif ext == 'avi':
                        wmv_lossless = options.get('wmv_lossless', False)
                        res = pack_avi(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                    elif ext == 'asf':
                        wmv_lossless = options.get('wmv_lossless', False)
                        res = pack_asf(fn, debug=options['debug'], quiet=quiet, lossless=wmv_lossless)
                    if res is not None:
                        results['files'].append([fn, res[1], res[2], res[3]])
                        outfile, insize, outsize, share = res
                        results['stats'][0] += 1
                        results['stats'][1] += insize
                        results['stats'][2] += outsize
        return results


    def repack_zip_file(self, filename, outfile=None,
                       def_options=None):
        """Repack single ZIP file """
        options = {"debug": False, 'pack_images': True, 'repack_archive': True, 'pack_archives': True,
                                 'deep_walking': True, 'log': False, 'quiet': False, 'ultra': False, 'dryrun': False}
        if def_options:
            for k in def_options.keys(): 
                options[k] = def_options[k]
        results = {'stats': [0, 0, 0], 'files': []}
        f_outfile = outfile
        dryrun = options.get('dryrun', False)
        if outfile is None: 
            if dryrun:
                # Use temporary file for dryrun
                tempname = uuid.uuid4().hex
                f_outfile = os.path.join(self.temppath, tempname + os.path.splitext(filename)[1])
            else:
                f_outfile = filename
        f_insize = os.path.getsize(filename)
        filetype = filename.rsplit('.', 1)[-1].lower()
        
        # Handle standalone parquet files (not ZIP-based)
        if filetype == 'parquet':
            ultra = options.get('ultra', False)
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_parquet = os.path.join(self.temppath, uuid.uuid4().hex + '.parquet')
                copyfile(filename, temp_parquet)
                res = pack_parquet(temp_parquet, debug=options.get('debug', False), quiet=options.get('quiet', False), ultra=ultra)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_parquet):
                        os.remove(temp_parquet)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_parquet):
                        os.remove(temp_parquet)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_parquet(filename, debug=options.get('debug', False), quiet=options.get('quiet', False), ultra=ultra)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_parquet failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone gzip files (not ZIP-based)
        if filetype == 'gz':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_gzip = os.path.join(self.temppath, uuid.uuid4().hex + '.gz')
                copyfile(filename, temp_gzip)
                res = pack_gzip(temp_gzip, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_gzip):
                        os.remove(temp_gzip)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_gzip):
                        os.remove(temp_gzip)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_gzip(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_gzip failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone xz files (not ZIP-based)
        if filetype == 'xz':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_xz = os.path.join(self.temppath, uuid.uuid4().hex + '.xz')
                copyfile(filename, temp_xz)
                res = pack_xz(temp_xz, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_xz):
                        os.remove(temp_xz)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_xz):
                        os.remove(temp_xz)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_xz(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_xz failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone bz2 files (not ZIP-based)
        if filetype == 'bz2':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_bz2 = os.path.join(self.temppath, uuid.uuid4().hex + '.bz2')
                copyfile(filename, temp_bz2)
                res = pack_bz2(temp_bz2, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_bz2):
                        os.remove(temp_bz2)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_bz2):
                        os.remove(temp_bz2)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_bz2(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_bz2 failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone PDF files
        if filetype == 'pdf':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_pdf = os.path.join(self.temppath, uuid.uuid4().hex + '.pdf')
                copyfile(filename, temp_pdf)
                res = pack_pdf(temp_pdf, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_pdf):
                        os.remove(temp_pdf)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_pdf):
                        os.remove(temp_pdf)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_pdf(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_pdf failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone GIF files
        if filetype == 'gif':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_gif = os.path.join(self.temppath, uuid.uuid4().hex + '.gif')
                copyfile(filename, temp_gif)
                res = pack_gif(temp_gif, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_gif):
                        os.remove(temp_gif)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_gif):
                        os.remove(temp_gif)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_gif(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_gif failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone WebP files
        if filetype == 'webp':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_webp = os.path.join(self.temppath, uuid.uuid4().hex + '.webp')
                copyfile(filename, temp_webp)
                res = pack_webp(temp_webp, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_webp):
                        os.remove(temp_webp)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_webp):
                        os.remove(temp_webp)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_webp(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_webp failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone SVG files
        if filetype == 'svg':
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_svg = os.path.join(self.temppath, uuid.uuid4().hex + '.svg')
                copyfile(filename, temp_svg)
                res = pack_svg(temp_svg, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_svg):
                        os.remove(temp_svg)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_svg):
                        os.remove(temp_svg)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_svg(filename, debug=options.get('debug', False), quiet=options.get('quiet', False))
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_svg failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone WMV files
        if filetype == 'wmv':
            wmv_lossless = options.get('wmv_lossless', False)
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_wmv = os.path.join(self.temppath, uuid.uuid4().hex + '.wmv')
                copyfile(filename, temp_wmv)
                res = pack_wmv(temp_wmv, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_wmv):
                        os.remove(temp_wmv)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_wmv):
                        os.remove(temp_wmv)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_wmv(filename, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_wmv failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone MP4 files
        if filetype == 'mp4':
            wmv_lossless = options.get('wmv_lossless', False)
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_mp4 = os.path.join(self.temppath, uuid.uuid4().hex + '.mp4')
                copyfile(filename, temp_mp4)
                res = pack_mp4(temp_mp4, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_mp4):
                        os.remove(temp_mp4)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_mp4):
                        os.remove(temp_mp4)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_mp4(filename, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_mp4 failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone AVI files
        if filetype == 'avi':
            wmv_lossless = options.get('wmv_lossless', False)
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_avi = os.path.join(self.temppath, uuid.uuid4().hex + '.avi')
                copyfile(filename, temp_avi)
                res = pack_avi(temp_avi, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_avi):
                        os.remove(temp_avi)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_avi):
                        os.remove(temp_avi)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_avi(filename, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_avi failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone ASF files
        if filetype == 'asf':
            wmv_lossless = options.get('wmv_lossless', False)
            if dryrun:
                # For dryrun, work with a copy
                from shutil import copyfile
                temp_asf = os.path.join(self.temppath, uuid.uuid4().hex + '.asf')
                copyfile(filename, temp_asf)
                res = pack_asf(temp_asf, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    # Clean up temp file
                    if os.path.exists(temp_asf):
                        os.remove(temp_asf)
                    return results
                else:
                    # Clean up temp file if it exists
                    if os.path.exists(temp_asf):
                        os.remove(temp_asf)
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
            else:
                res = pack_asf(filename, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                if res is not None:
                    outfile, insize, outsize, share = res
                    results['final'] = [insize, outsize, share]
                    results['files'].append([filename, insize, outsize, share])
                    return results
                else:
                    # If pack_asf failed, return None or empty results
                    results['final'] = [f_insize, f_insize, 0.0]
                    return results
        
        # Handle standalone 7z files (archive format, needs extraction and repacking)
        if filetype == '7z':
            # Extract, process contents, and repack as 7z with maximum compression
            rnd = random.randint(1, 1000)
            tempname = uuid.uuid4().hex
            fpath = os.path.join(self.temppath, tempname)
            os.mkdir(fpath)
            fn = SZIP_PATH + ' x -y -o%s "%s"' % (fpath, filename)
            if options['quiet']:
                if os.name == 'nt':  # Windows
                    fn = fn + ' > nul 2>&1'
                else:  # Unix-like
                    fn = fn + ' > /dev/null 2>&1'
            if options['debug']:
                logging.debug('Extracting 7z file: %s' % fn)
            os.system(fn)
            
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
                                    res = pack_jpg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), jpeg_quality=options.get('jpeg_quality'))
                            elif ext in ['png', ]:
                                if options['pack_images']:
                                    res = pack_png(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), png_quality=options.get('png_quality'))
                            elif ext == 'parquet':
                                ultra = options.get('ultra', False)
                                res = pack_parquet(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), ultra=ultra)
                            elif ext == 'gz':
                                res = pack_gzip(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'xz':
                                res = pack_xz(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'bz2':
                                res = pack_bz2(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'pdf':
                                res = pack_pdf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'gif':
                                res = pack_gif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'webp':
                                res = pack_webp(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'svg':
                                res = pack_svg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext in ['tif', 'tiff']:
                                res = pack_tif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'wmv':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_wmv(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'mp4':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_mp4(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'avi':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_avi(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'asf':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_asf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            if res is not None:
                                results['files'].append([name, res[1], res[2], res[3]])
                                outfile, insize, outsize, share = res
                                results['stats'][0] += 1
                                results['stats'][1] += insize
                                results['stats'][2] += outsize
            
            # Repack as 7z with maximum compression
            if dryrun:
                rpath = os.path.abspath(f_outfile)
            else:
                rpath = os.path.abspath(filename)
            compression_level = options.get('compression_level', 9)
            fn = self.toolpath + ' -t7z -y -mx%d a "%s" *' % (compression_level, rpath)
            if options['quiet']:
                if os.name == 'nt':  # Windows
                    fn = fn + ' > nul 2>&1'
                else:  # Unix-like
                    fn = fn + ' > /dev/null 2>&1'
            if options['debug']:
                logging.debug('Repacking 7z file: %s' % fn)
            # Execute 7z repacking cmd
            os.chdir(fpath)
            os.system(fn)
            os.chdir(self.currpath)
            rmtree(fpath)
            # Calc size gains
            outsize = os.path.getsize(f_outfile)
            share = (f_insize - outsize) * 100.0 / f_insize if f_insize > 0 else 0
            if not options['quiet']:
                if dryrun:
                    logging.debug('File %s would shrink %d -> %d (%f%%) [DRYRUN]' % (filename.encode('utf8'), f_insize, outsize, share))
                else:
                    logging.debug('File %s shrinked %d -> %d (%f%%)' % (f_outfile.encode('utf8'), f_insize, outsize, share))
            results['final'] = [f_insize, outsize, share]
            # Clean up temporary output file in dryrun mode
            if dryrun and os.path.exists(f_outfile) and f_outfile != filename:
                os.remove(f_outfile)
            return results
        
        # Handle standalone RAR files (archive format, needs extraction and repacking)
        if filetype == 'rar':
            # Check if rar tool is available
            rar_path = which(RAR_PATH)
            if not rar_path:
                if not options['quiet']:
                    logging.warning('rar tool not found. RAR files can be extracted but not recompressed. Install WinRAR or rar command-line tool to enable RAR recompression.')
                # Still extract and optimize contents, but recompress as 7z
                use_7z_fallback = True
            else:
                use_7z_fallback = False
            
            # Extract, process contents, and repack as RAR (or 7z if rar tool unavailable)
            rnd = random.randint(1, 1000)
            tempname = uuid.uuid4().hex
            fpath = os.path.join(self.temppath, tempname)
            os.mkdir(fpath)
            
            # Try to extract using unrar first, fall back to 7zz if unrar is not available
            unrar_path = which(UNRAR_PATH)
            if unrar_path:
                # Extract using unrar (preferred for RAR files)
                # unrar x archive.rar extracts to current directory
                # Use absolute path for filename since we're changing directories
                abs_filename = abspath(filename)
                # Change to output directory first, then extract
                os.chdir(fpath)
                fn = unrar_path + ' x -y "%s"' % abs_filename
                if options['quiet']:
                    if os.name == 'nt':  # Windows
                        fn = fn + ' > nul 2>&1'
                    else:  # Unix-like
                        fn = fn + ' > /dev/null 2>&1'
                if options['debug']:
                    logging.debug('Extracting RAR file with unrar: %s' % fn)
                os.system(fn)
                os.chdir(self.currpath)
            else:
                # Fall back to 7zz if unrar is not available
                if not options['quiet']:
                    logging.warning('unrar tool not found, using 7zz for RAR extraction. Install unrar for better RAR support.')
                fn = SZIP_PATH + ' x -y -o%s "%s"' % (fpath, filename)
                if options['quiet']:
                    if os.name == 'nt':  # Windows
                        fn = fn + ' > nul 2>&1'
                    else:  # Unix-like
                        fn = fn + ' > /dev/null 2>&1'
                if options['debug']:
                    logging.debug('Extracting RAR file with 7zz: %s' % fn)
                os.system(fn)
            
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
                                    res = pack_jpg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), jpeg_quality=options.get('jpeg_quality'))
                            elif ext in ['png', ]:
                                if options['pack_images']:
                                    res = pack_png(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), png_quality=options.get('png_quality'))
                            elif ext == 'parquet':
                                ultra = options.get('ultra', False)
                                res = pack_parquet(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), ultra=ultra)
                            elif ext == 'gz':
                                res = pack_gzip(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'xz':
                                res = pack_xz(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'bz2':
                                res = pack_bz2(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'pdf':
                                res = pack_pdf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'gif':
                                res = pack_gif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'webp':
                                res = pack_webp(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'svg':
                                res = pack_svg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext in ['tif', 'tiff']:
                                res = pack_tif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'wmv':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_wmv(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'mp4':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_mp4(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'avi':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_avi(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'asf':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_asf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            if res is not None:
                                results['files'].append([name, res[1], res[2], res[3]])
                                outfile, insize, outsize, share = res
                                results['stats'][0] += 1
                                results['stats'][1] += insize
                                results['stats'][2] += outsize
            
            # Repack as RAR with maximum compression (or 7z if rar tool unavailable)
            if dryrun:
                rpath = os.path.abspath(f_outfile)
            else:
                rpath = os.path.abspath(filename)
            
            if use_7z_fallback:
                # Fallback to 7z compression if rar tool is not available
                compression_level = options.get('compression_level', 9)
                # Create 7z file with .7z extension
                if dryrun:
                    rpath_7z = f_outfile.rsplit('.', 1)[0] + '.7z'
                else:
                    rpath_7z = rpath.rsplit('.', 1)[0] + '.7z'
                fn = self.toolpath + ' -t7z -y -mx%d a "%s" *' % (compression_level, rpath_7z)
                if options['quiet']:
                    if os.name == 'nt':  # Windows
                        fn = fn + ' > nul 2>&1'
                    else:  # Unix-like
                        fn = fn + ' > /dev/null 2>&1'
                if options['debug']:
                    logging.debug('Repacking RAR file as 7z (rar tool not available): %s' % fn)
                rpath = rpath_7z
            else:
                # Use rar tool for recompression
                # RAR compression levels: -m0 (store), -m1 (fastest), -m2, -m3, -m4, -m5 (default), 5 (best)
                # Map compression_level (1-9) to RAR levels: 1-2 -> -m3, 3-4 -> -m4, 5-6 -> -m5, 7-9 -> -m6
                compression_level = options.get('compression_level', 9)
                if compression_level <= 2:
                    rar_level = '-m3'
                elif compression_level <= 4:
                    rar_level = '-m4'
                elif compression_level <= 6:
                    rar_level = '-m5'
                else:
                    rar_level = '-m5'  # Best compression
                
                # RAR command: rar a -r -inul -m6 output.rar *
                # -a: add files, -r: recurse subdirectories, -inul: suppress messages, -m6: best compression
                fn = rar_path + ' a -r ' + rar_level + ' -y "%s" *' % rpath
                if options['quiet']:
                    if os.name == 'nt':  # Windows
                        fn = fn + ' > nul 2>&1'
                    else:  # Unix-like
                        fn = fn + ' > /dev/null 2>&1'
                if options['debug']:
                    logging.debug('Repacking RAR file: %s' % fn)
            
            # Execute repacking cmd
            os.chdir(fpath)
            os.system(fn)
            os.chdir(self.currpath)
            rmtree(fpath)
            
            # Calc size gains
            if use_7z_fallback:
                # If we created a 7z file, use that path
                outsize = os.path.getsize(rpath) if os.path.exists(rpath) else f_insize
            else:
                outsize = os.path.getsize(f_outfile) if os.path.exists(f_outfile) else f_insize
            share = (f_insize - outsize) * 100.0 / f_insize if f_insize > 0 else 0
            if not options['quiet']:
                if dryrun:
                    if use_7z_fallback:
                        logging.debug('File %s would be converted to 7z and shrink %d -> %d (%f%%) [DRYRUN]' % (filename.encode('utf8'), f_insize, outsize, share))
                    else:
                        logging.debug('File %s would shrink %d -> %d (%f%%) [DRYRUN]' % (filename.encode('utf8'), f_insize, outsize, share))
                else:
                    if use_7z_fallback:
                        logging.debug('File %s converted to 7z and shrinked %d -> %d (%f%%)' % (rpath.encode('utf8'), f_insize, outsize, share))
                        # Remove original RAR file if conversion was successful
                        if os.path.exists(filename) and filename != rpath:
                            try:
                                os.remove(filename)
                            except Exception:
                                pass
                    else:
                        logging.debug('File %s shrinked %d -> %d (%f%%)' % (f_outfile.encode('utf8'), f_insize, outsize, share))
            results['final'] = [f_insize, outsize, share]
            # Clean up temporary output file in dryrun mode
            if dryrun and os.path.exists(f_outfile) and f_outfile != filename:
                os.remove(f_outfile)
            return results
        
        rnd = random.randint(1, 1000)
        tempname = uuid.uuid4().hex
        if filetype in SUPPORTED_EXTS:
            fpath = os.path.join(self.temppath, tempname)  # os.path.basename(filename) + '_' + str(rnd)
            os.mkdir(fpath)
            fn = SZIP_PATH + ' x -y -o%s "%s"' % (fpath, filename)
            if options['quiet']:
                fn = fn + ' > /dev/null 2>&1'
            if options['debug']:
                logging.debug('Filename %s' % fn)
            os.system(fn)
            if options['debug']:
                logging.info('Filetype %s' % str(filetype))
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
                                    res = pack_jpg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), jpeg_quality=options.get('jpeg_quality'))
                            elif ext in ['png', ]:
                                if options['pack_images']:
                                    res = pack_png(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), png_quality=options.get('png_quality'))
                            elif ext == 'parquet':
                                ultra = options.get('ultra', False)
                                res = pack_parquet(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), ultra=ultra)
                            elif ext == 'gz':
                                res = pack_gzip(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'xz':
                                res = pack_xz(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'bz2':
                                res = pack_bz2(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'pdf':
                                res = pack_pdf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'gif':
                                res = pack_gif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'webp':
                                res = pack_webp(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'svg':
                                res = pack_svg(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext in ['tif', 'tiff']:
                                res = pack_tif(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False))
                            elif ext == 'wmv':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_wmv(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'mp4':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_mp4(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'avi':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_avi(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
                            elif ext == 'asf':
                                wmv_lossless = options.get('wmv_lossless', False)
                                res = pack_asf(fullname, debug=options.get('debug', False), quiet=options.get('quiet', False), lossless=wmv_lossless)
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

#            if filetype in ZIP_SENSITIVE_EXTS:
#                fn = ZIP_PATH + ' -r -q -9 "%s" *' % (rpath,)
#            else:
            # Use temporary output file for dryrun
            if dryrun:
                rpath = os.path.abspath(f_outfile)
            else:
                rpath = os.path.abspath(filename)
            compression_level = options.get('compression_level', 9)
            fn = self.toolpath + ' -tzip -y -mx%d a "%s" *' % (compression_level, rpath)
            if options['quiet']:
                fn = fn + ' > /dev/null 2>&1'
            # Execute zip shrinking cmd
            os.chdir(fpath)
            os.system(fn)
            os.chdir(self.currpath)
            rmtree(fpath)
            # Calc size gains
            outsize = os.path.getsize(f_outfile)
            share = (f_insize - outsize) * 100.0 / f_insize if f_insize > 0 else 0
            if not options['quiet']:
                if dryrun:
                    logging.debug('File %s would shrink %d -> %d (%f%%) [DRYRUN]' % (filename.encode('utf8'), f_insize, outsize, share))
                else:
                    logging.debug('File %s shrinked %d -> %d (%f%%)' % (f_outfile.encode('utf8'), f_insize, outsize, share))
            results['final'] = [f_insize, outsize, share]
            # Clean up temporary output file in dryrun mode
            if dryrun and os.path.exists(f_outfile) and f_outfile != filename:
                os.remove(f_outfile)
            return results

if __name__ == "__main__":
	dr = FileRepacker()
	results = dr.repack_zip_file(sys.argv[1])

