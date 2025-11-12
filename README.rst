About
=====

This tool and library were written to optimize Microsoft Word / Libreoffice ZIP based files. It uses 7-Zip, jpegoptim
and pngquant and recompresses not only host zip file but also all images and other suitable files inside it.

============
Installation
============

At the command line::

    $ pip install filerepack

Or, if you don't have pip installed::

    $ easy_install filerepack

If you want to install from the latest sources, you can do::

    $ git clone https://github.com/ivbeg/filerepack.git
    $ cd  filerepack
    $ python setup.py filerepack




============
Command line
============

Usage: filerepack FILENAME

  docx to csv convertor (http://github.com/ivbeg/filesrepack)
  Repacks ZIP and ZIP'based files and images for better compression

  Use command: "filerepack <filename>" to run recompression.

Examples
========
filerepack CP_CONTRACT_160166.docx

Recompresses CP_CONTRACT_160166.docx including all zip files, images and so on


Code
====


Repacks presentation file "some_presentation.pptx
    >>> from filerepack import FileRepacker
    >>> rp = FileRepacker()
    >>> stats = rp.repack_zip_file(filename="some_presentation.pptx")


Recursively repacks all images .jpg and .png files in directory "some_media_path"
    >>> from filerepack import FileRepacker
    >>> rp = FileRepacker()
    >>> stats = rp.pack_images('some_media_path', recursive=True)



Requirements
============
It works in both Windows and Linux environments.
You need to install zip, 7Zip, jpegoptim and pngquant tools in your OS PATH settings.


Acknowledgements
================
