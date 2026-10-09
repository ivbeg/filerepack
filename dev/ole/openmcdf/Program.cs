// Qualification only: always consolidate a private copy, never the source.
using System.IO;
using OpenMcdf;

File.Copy(args[0], args[1], overwrite: false);
using var root = RootStorage.Open(args[1], FileMode.Open, FileAccess.ReadWrite);
root.Flush(consolidate: true);
