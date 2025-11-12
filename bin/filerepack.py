#!/usr/bin/env python
#-*- coding: utf-8 -*-

import os
from os.path import isfile, join, exists
from os import walk
import typer
from filerepack import FileRepacker
from filerepack.consts import SUPPORTED_EXTS

app = typer.Typer()


@app.command()
def repack(
    filename: str = typer.Argument(..., help="Path to the file to repack"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Calculate space savings without modifying files")
):
    """
    Repacks a single file for higher compression.
    """
    if not exists(filename):
        typer.echo(f"Error: File '{filename}' does not exist.", err=True)
        raise typer.Exit(1)
    
    if not isfile(filename):
        typer.echo(f"Error: '{filename}' is not a file.", err=True)
        raise typer.Exit(1)
    
    dr = FileRepacker()
    results = dr.repack_zip_file(filename, def_options={'debug': True, 'dryrun': dryrun})
    
    if dryrun:
        typer.echo(f"[DRYRUN] File {filename} would shrink {results['final'][0]} -> {results['final'][1]} ({results['final'][2]:.2f}%)")
    else:
        typer.echo(f"File {filename} shrinked {results['final'][0]} -> {results['final'][1]} ({results['final'][2]:.2f}%)")
    
    if len(results['files']) > 0:
        typer.echo('Files recompressed:')
        for fdata in results['files']:
            typer.echo(f"- {fdata[0]}: {fdata[1]} -> {fdata[2]} ({fdata[3]:.2f}%)")


@app.command()
def bulk(
    directory: str = typer.Argument(..., help="Directory path to recursively repack all supported files"),
    dryrun: bool = typer.Option(False, "--dryrun", help="Calculate space savings without modifying files")
):
    """
    Recursively repacks all supported files in the selected directory.
    """
    if not exists(directory):
        typer.echo(f"Error: Directory '{directory}' does not exist.", err=True)
        raise typer.Exit(1)
    
    if not os.path.isdir(directory):
        typer.echo(f"Error: '{directory}' is not a directory.", err=True)
        raise typer.Exit(1)
    
    if dryrun:
        typer.echo("[DRYRUN MODE] Files will not be modified.")
    
    dr = FileRepacker()
    files_processed = 0
    files_failed = 0
    total_original_size = 0
    total_final_size = 0
    
    typer.echo(f"Scanning directory: {directory}")
    
    for root, dirs, files in walk(directory):
        for file in files:
            ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
            if ext in SUPPORTED_EXTS:
                filepath = join(root, file)
                try:
                    typer.echo(f"Processing: {filepath}")
                    results = dr.repack_zip_file(filepath, def_options={'debug': False, 'quiet': True, 'dryrun': dryrun})
                    if results and 'final' in results:
                        original_size = results['final'][0]
                        final_size = results['final'][1]
                        total_original_size += original_size
                        total_final_size += final_size
                        if dryrun:
                            typer.echo(f"  ✓ {filepath}: {original_size} -> {final_size} ({results['final'][2]:.2f}%) [DRYRUN]")
                        else:
                            typer.echo(f"  ✓ {filepath}: {original_size} -> {final_size} ({results['final'][2]:.2f}%)")
                        files_processed += 1
                    else:
                        typer.echo(f"  ✗ {filepath}: Failed to repack", err=True)
                        files_failed += 1
                except Exception as e:
                    typer.echo(f"  ✗ {filepath}: Error - {str(e)}", err=True)
                    files_failed += 1
    
    # Format sizes for display
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    # Calculate space gains
    total_saved = total_original_size - total_final_size
    if total_original_size > 0:
        percent_saved = (total_saved * 100.0) / total_original_size
    else:
        percent_saved = 0.0
    
    typer.echo(f"\nSummary:")
    typer.echo(f"  Files processed successfully: {files_processed}")
    typer.echo(f"  Files failed: {files_failed}")
    if files_processed > 0:
        typer.echo(f"  Original total size: {format_size(total_original_size)}")
        typer.echo(f"  Final total size: {format_size(total_final_size)}")
        if dryrun:
            typer.echo(f"  Space that would be saved: {format_size(total_saved)} ({percent_saved:.2f}%) [DRYRUN]")
        else:
            typer.echo(f"  Space saved: {format_size(total_saved)} ({percent_saved:.2f}%)")


if __name__ == "__main__":
    app()
