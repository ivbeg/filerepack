//! The Python caller owns eligibility, independent verification and publication.
use std::env;
use std::fs::{File, OpenOptions};
use std::io::{self, BufReader, BufWriter, Read, Write};
use std::path::Path;

const LIMIT: u64 = 128 * 1024 * 1024;
const PNG_LIMIT: u64 = 16 * 1024 * 1024;

// This independent row decoder consumes already framed/bounded filtered bytes,
// never PNG encoder claims. It retains two rows and does not allocate an image.
fn png_rows(
    input: &mut impl Read,
    output: &mut impl Write,
    width: usize,
    height: usize,
    color: usize,
    palette: usize,
) -> io::Result<()> {
    let step: usize = match color {
        0 | 3 => 1,
        2 => 3,
        4 => 2,
        6 => 4,
        _ => return Err(io::Error::other("Unqualified PNG color mode")),
    };
    let stride = width
        .checked_mul(step)
        .ok_or_else(|| io::Error::other("PNG width overflow"))?;
    let size = stride.checked_add(1).and_then(|n| n.checked_mul(height));
    if width == 0
        || height == 0
        || size.is_none_or(|n| n as u64 > PNG_LIMIT)
        || (color == 3 && !(1..=256).contains(&palette))
        || (color != 3 && palette != 0)
    {
        return Err(io::Error::other("PNG row bounds"));
    }
    let mut previous = vec![0u8; stride];
    let mut row = vec![0u8; stride];
    for _ in 0..height {
        let mut filter = [0u8];
        input.read_exact(&mut filter)?;
        if filter[0] > 4 {
            return Err(io::Error::other("Invalid PNG filter"));
        }
        input.read_exact(&mut row)?;
        for i in 0..stride {
            let a = if i >= step { row[i - step] } else { 0 };
            let b = previous[i];
            let c = if i >= step { previous[i - step] } else { 0 };
            let predictor = match filter[0] {
                0 => 0,
                1 => a,
                2 => b,
                3 => ((u16::from(a) + u16::from(b)) / 2) as u8,
                4 => {
                    let p = i32::from(a) + i32::from(b) - i32::from(c);
                    let pa = (p - i32::from(a)).abs();
                    let pb = (p - i32::from(b)).abs();
                    let pc = (p - i32::from(c)).abs();
                    if pa <= pb && pa <= pc {
                        a
                    } else if pb <= pc {
                        b
                    } else {
                        c
                    }
                }
                _ => unreachable!(),
            };
            row[i] = row[i].wrapping_add(predictor);
            if color == 3 && usize::from(row[i]) >= palette {
                return Err(io::Error::other("PNG palette index outside table"));
            }
        }
        output.write_all(&row)?;
        std::mem::swap(&mut row, &mut previous);
    }
    let mut tail = [0u8];
    if input.read(&mut tail)? != 0 {
        return Err(io::Error::other("Extra PNG filtered bytes"));
    }
    output.flush()
}

fn png_unfilter(args: &[std::ffi::OsString]) -> io::Result<()> {
    let numbers: Vec<usize> = args[2..6]
        .iter()
        .map(|v| {
            v.to_str()
                .and_then(|s| s.parse().ok())
                .ok_or_else(|| io::Error::other("Invalid PNG dimensions"))
        })
        .collect::<io::Result<_>>()?;
    let input = File::open(&args[6])?;
    if input.metadata()?.len() > PNG_LIMIT {
        return Err(io::Error::other("PNG input exceeds 16 MiB"));
    }
    let output = OpenOptions::new().write(true).open(&args[7])?;
    if output.metadata()?.len() != 0 {
        return Err(io::Error::other("PNG destination must be empty"));
    }
    png_rows(
        &mut BufReader::new(input),
        &mut BufWriter::new(output),
        numbers[0],
        numbers[1],
        numbers[2],
        numbers[3],
    )
}

// Only the observed slot-zero R/length-2 service-name anomaly is repaired.
// All other directory fields and names still pass cfb::open_strict.
fn normalize_root_name(data: &mut [u8]) {
    if data.len() < 512
        || data[..8] != [0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]
        || data[26..34] != [3, 0, 0xfe, 0xff, 9, 0, 6, 0]
    {
        return;
    }
    let sid = u32::from_le_bytes(data[48..52].try_into().unwrap());
    let offset = (u64::from(sid) + 1) * 512;
    if offset + 128 > data.len() as u64 {
        return;
    }
    let root = &mut data[offset as usize..offset as usize + 128];
    if root[..2] != [b'R', 0] || root[2..64].iter().any(|&b| b != 0) || root[64..67] != [2, 0, 5] {
        return;
    }
    for (index, unit) in "Root Entry".encode_utf16().enumerate() {
        root[index * 2..index * 2 + 2].copy_from_slice(&unit.to_le_bytes());
    }
    root[64..66].copy_from_slice(&22u16.to_le_bytes());
}

fn open_source(source: &Path) -> io::Result<cfb::CompoundFile<io::Cursor<Vec<u8>>>> {
    let input = File::open(source)?;
    let size = input.metadata()?.len();
    if size > LIMIT {
        return Err(io::Error::other("CFB input exceeds 128 MiB"));
    }
    // Avoid transient old/new whole-carrier buffers during geometric growth.
    let mut data = Vec::with_capacity(size as usize);
    input.take(size + 1).read_to_end(&mut data)?;
    if data.len() as u64 != size {
        return Err(io::Error::other("CFB input length changed"));
    }
    normalize_root_name(&mut data);
    cfb::CompoundFile::open_strict(io::Cursor::new(data))
}

fn replacement_input(path: &Path, limit: u64) -> io::Result<(File, u64)> {
    let input = File::open(path)?;
    let size = input.metadata()?.len();
    if size == 0 || size > limit {
        return Err(io::Error::other("Invalid root-stream replacement size"));
    }
    Ok((input, size))
}

fn copy_replacement(input: &mut impl Read, size: u64, output: &mut impl Write) -> io::Result<()> {
    // A staged stream is consumed once. Bound growth as well as truncation;
    // never hold every prepared stream alongside the whole source carrier.
    let copied = io::copy(&mut input.take(size + 1), output)?;
    if copied != size {
        return Err(io::Error::other("Root-stream replacement length changed"));
    }
    Ok(())
}

fn replacement(path: &Path, limit: u64) -> io::Result<Vec<u8>> {
    let (mut input, size) = replacement_input(path, limit)?;
    let mut data = Vec::new();
    copy_replacement(&mut input, size, &mut data)?;
    Ok(data)
}

fn compact(source: &Path, destination: &Path, plan: &[(&str, &Path)]) -> io::Result<()> {
    let mut original = open_source(source)?;
    if original.version() != cfb::Version::V3 {
        return Err(io::Error::other("Only CFB version 3 is qualified"));
    }
    let entries: Vec<_> = original.walk().collect();
    if entries.len() > 8192 {
        return Err(io::Error::other("CFB directory entry limit exceeded"));
    }
    // CLI modes below supply fixed, unique names, never an arbitrary user path.
    let mut replacements = Vec::new();
    for (name, path) in plan {
        if !original.is_stream(format!("/{name}")) {
            return Err(io::Error::other("Missing named replacement root stream"));
        }
        let limit = if *name == "Current User" { 4096 } else { LIMIT };
        replacements.push((*name, replacement_input(path, limit)?));
    }
    let mut total = 0;
    for entry in &entries {
        if entry.is_stream() {
            let replacement = replacements
                .iter()
                .find(|(name, _)| entry.path() == Path::new(&format!("/{name}")));
            total += replacement.map_or(entry.len(), |(_, (_, size))| *size);
            if total > LIMIT {
                return Err(io::Error::other("CFB stream byte limit exceeded"));
            }
        }
    }
    // The caller supplies an owned, empty staging file. Refuse other destinations.
    let output = OpenOptions::new()
        .read(true)
        .write(true)
        .open(destination)?;
    if output.metadata()?.len() != 0 {
        return Err(io::Error::other(
            "Destination must be an empty staging file",
        ));
    }
    let mut rebuilt = cfb::CompoundFile::create_with_version(cfb::Version::V3, output)?;
    for entry in &entries {
        if entry.is_root() {
            continue;
        }
        if entry.is_storage() {
            rebuilt.create_storage(entry.path())?;
        } else {
            // CFB paths use the platform's separators. Match only root entries,
            // so nested streams with these names are copied unchanged as well.
            let replacement = replacements
                .iter_mut()
                .find(|(name, _)| entry.path() == Path::new(&format!("/{name}")));
            let mut output = rebuilt.create_new_stream(entry.path())?;
            if let Some((_, (input, size))) = replacement {
                copy_replacement(input, *size, &mut output)?;
            } else {
                let mut input = original.open_stream(entry.path())?;
                let copied = io::copy(&mut input, &mut output)?;
                if copied != entry.len() {
                    return Err(io::Error::other("Truncated CFB source stream"));
                }
            }
            output.flush()?;
        }
    }
    // Writes/creation can touch timestamps. Restore all metadata last.
    for entry in entries.iter().rev() {
        rebuilt.set_state_bits(entry.path(), entry.state_bits())?;
        if !entry.is_stream() {
            rebuilt.set_storage_clsid(entry.path(), *entry.clsid())?;
            rebuilt.set_created_time(entry.path(), entry.created())?;
            rebuilt.set_modified_time(entry.path(), entry.modified())?;
        }
    }
    rebuilt.flush()?;
    rebuilt.into_inner().sync_all()
}

// A bounded binary plan. Host scopes are fixed; source entries must already exist.
// Python independently resolves and verifies every selected path and intended change.
fn qualified_path(host: &str, name: &str) -> bool {
    let parts: Vec<_> = name.split('/').collect();
    if parts
        .iter()
        .any(|p| p.is_empty() || *p == "." || *p == ".." || p.contains(['\\', '\0']))
    {
        return false;
    }
    match host {
        "doc" => parts.len() == 1 && matches!(name, "WordDocument" | "Data" | "0Table" | "1Table"),
        "xls" => name == "Workbook",
        "ppt" => matches!(name, "PowerPoint Document" | "Pictures" | "Current User"),
        "hwp" => {
            name == "DocInfo"
                || (parts.len() == 2
                    && ((parts[0] == "BodyText"
                        && parts[1].strip_prefix("Section").is_some_and(|s| {
                            !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit())
                        }))
                        || (parts[0] == "BinData"
                            && parts[1].starts_with("BIN")
                            && parts[1]
                                .bytes()
                                .all(|c| c.is_ascii_alphanumeric() || c == b'.'))))
        }
        "doc-object" => {
            parts.len() >= 3
                && parts[0] == "ObjectPool"
                && parts[1]
                    .strip_prefix('_')
                    .is_some_and(|s| !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit()))
        }
        "xls-object" => {
            parts.len() >= 2
                && parts[0]
                    .strip_prefix("MBD")
                    .is_some_and(|s| s.len() == 8 && s.bytes().all(|c| c.is_ascii_hexdigit()))
        }
        _ => false,
    }
}

fn planned(host: &str, plan: &Path, source: &Path, destination: &Path) -> io::Result<()> {
    let input = replacement(plan, 1024 * 1024)?;
    if input.len() < 12 || &input[..8] != b"FRPLAN01" {
        return Err(io::Error::other("Invalid plan version"));
    }
    let mut at = 8;
    let count = u32::from_le_bytes(input[at..at + 4].try_into().unwrap()) as usize;
    at += 4;
    if count == 0 || count > 8192 {
        return Err(io::Error::other("Plan count limit"));
    }
    let mut owned = Vec::new();
    for _ in 0..count {
        if at + 4 > input.len() {
            return Err(io::Error::other("Truncated plan"));
        }
        let a = u16::from_le_bytes(input[at..at + 2].try_into().unwrap()) as usize;
        let b = u16::from_le_bytes(input[at + 2..at + 4].try_into().unwrap()) as usize;
        at += 4;
        if a == 0 || b == 0 || at + a + b > input.len() {
            return Err(io::Error::other("Plan path bounds"));
        }
        let name = std::str::from_utf8(&input[at..at + a])
            .map_err(io::Error::other)?
            .to_owned();
        at += a;
        let file = std::str::from_utf8(&input[at..at + b])
            .map_err(io::Error::other)?
            .to_owned();
        at += b;
        if !qualified_path(host, &name) || owned.iter().any(|(n, _)| n == &name) {
            return Err(io::Error::other(
                "Unqualified or duplicate replacement path",
            ));
        }
        owned.push((name, file));
    }
    if at != input.len() {
        return Err(io::Error::other("Trailing plan bytes"));
    }
    let refs: Vec<_> = owned
        .iter()
        .map(|(name, file)| (name.as_str(), Path::new(file)))
        .collect();
    compact(source, destination, &refs)
}

fn extract_object(host: &str, name: &str, source: &Path, destination: &Path) -> io::Result<()> {
    if !qualified_path(host, &format!("{name}/sentinel")) {
        return Err(io::Error::other("Unqualified object scope"));
    }
    let mut original = open_source(source)?;
    if original.version() != cfb::Version::V3 {
        return Err(io::Error::other("CFB version"));
    }
    let prefix = format!("/{name}");
    let root = original.entry(&prefix)?;
    if !root.is_storage() {
        return Err(io::Error::other("Object is not a storage"));
    }
    let entries: Vec<_> = original.walk_storage(&prefix)?.collect();
    if entries.len() > 8192 || entries.iter().map(|e| e.len()).sum::<u64>() > LIMIT {
        return Err(io::Error::other("Object limit"));
    }
    let output = OpenOptions::new()
        .read(true)
        .write(true)
        .open(destination)?;
    if output.metadata()?.len() != 0 {
        return Err(io::Error::other("Nonempty staging file"));
    }
    let mut rebuilt = cfb::CompoundFile::create_with_version(cfb::Version::V3, output)?;
    for entry in &entries {
        let relative = entry
            .path()
            .strip_prefix(&prefix)
            .map_err(io::Error::other)?;
        if relative.as_os_str().is_empty() {
            continue;
        }
        let target = Path::new("/").join(relative);
        if entry.is_storage() {
            rebuilt.create_storage(&target)?;
        } else {
            let mut input = original.open_stream(entry.path())?;
            let mut output = rebuilt.create_new_stream(&target)?;
            if io::copy(&mut input, &mut output)? != entry.len() {
                return Err(io::Error::other("Truncated object"));
            }
        }
    }
    for entry in entries.iter().rev() {
        let relative = entry
            .path()
            .strip_prefix(&prefix)
            .map_err(io::Error::other)?;
        let target = Path::new("/").join(relative);
        rebuilt.set_state_bits(&target, entry.state_bits())?;
        if !entry.is_stream() {
            rebuilt.set_storage_clsid(&target, *entry.clsid())?;
            if !relative.as_os_str().is_empty() {
                rebuilt.set_created_time(&target, entry.created())?;
            }
            rebuilt.set_modified_time(&target, entry.modified())?;
        }
    }
    rebuilt.flush()?;
    rebuilt.into_inner().sync_all()
}

fn main() {
    let args: Vec<_> = env::args_os().collect();
    if args.len() == 2 && args[1] == "--version" {
        println!("filerepack-ole {} (cfb 0.14.0)", env!("CARGO_PKG_VERSION"));
        return;
    }
    if args.len() == 2 && args[1] == "--capabilities" {
        println!("compact-v3 ppt-stream-replacement-v1 officeart-stream-replacement-v1 qualified-stream-replacement-v1 qualified-object-extraction-v1 png-unfilter-v1");
        return;
    }
    let result = if args.len() == 8 && args[1] == "--png-unfilter-v1" {
        png_unfilter(&args)
    } else if args.len() == 3 {
        compact(args[1].as_ref(), args[2].as_ref(), &[])
    } else if args.len() == 6 && args[1] == "--extract-qualified-object-v1" {
        match (args[2].to_str(), args[3].to_str()) {
            (Some(host), Some(name)) => {
                extract_object(host, name, args[4].as_ref(), args[5].as_ref())
            }
            _ => Err(io::Error::other("Invalid object path")),
        }
    } else if args.len() == 6 && args[1] == "--replace-qualified-streams-v1" {
        match args[2].to_str() {
            Some(host) => planned(host, args[3].as_ref(), args[4].as_ref(), args[5].as_ref()),
            None => Err(io::Error::other("Invalid host")),
        }
    } else if args.len() == 6 && args[1] == "--replace-ppt-streams" {
        compact(
            args[4].as_ref(),
            args[5].as_ref(),
            &[
                ("PowerPoint Document", args[2].as_ref()),
                ("Current User", args[3].as_ref()),
            ],
        )
    } else if args.len() == 6 && args[1] == "--replace-officeart-streams" && args[2] == "xls" {
        compact(
            args[4].as_ref(),
            args[5].as_ref(),
            &[("Workbook", args[3].as_ref())],
        )
    } else if args.len() == 7 && args[1] == "--replace-officeart-streams" && args[2] == "doc" {
        compact(
            args[5].as_ref(),
            args[6].as_ref(),
            &[
                ("WordDocument", args[3].as_ref()),
                ("Data", args[4].as_ref()),
            ],
        )
    } else if args.len() == 7 && args[1] == "--replace-officeart-streams" && args[2] == "ppt" {
        compact(
            args[5].as_ref(),
            args[6].as_ref(),
            &[
                ("PowerPoint Document", args[3].as_ref()),
                ("Pictures", args[4].as_ref()),
            ],
        )
    } else {
        eprintln!("Usage: filerepack-ole [--replace-ppt-streams DOCUMENT CURRENT-USER | --replace-officeart-streams doc WORD DATA | xls WORKBOOK | ppt DOCUMENT PICTURES] SOURCE EMPTY-STAGING-FILE");
        std::process::exit(2);
    };
    if let Err(error) = result {
        eprintln!("OLE compaction failed: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::{copy_replacement, normalize_root_name, png_rows, qualified_path};
    use std::io::Cursor;

    #[test]
    fn png_filters_preserve_exact_rows() {
        for (filter, first, second) in [
            (0, [3, 5, 7, 9], [3, 5, 7, 9]),
            (1, [3, 2, 2, 2], [3, 2, 2, 2]),
            (2, [3, 5, 7, 9], [0, 0, 0, 0]),
            (3, [3, 4, 5, 6], [2, 1, 1, 1]),
            (4, [3, 2, 2, 2], [0, 0, 0, 0]),
        ] {
            let raw: Vec<u8> =
                [vec![filter], first.to_vec(), vec![filter], second.to_vec()].concat();
            let mut samples = Vec::new();
            png_rows(&mut Cursor::new(raw), &mut samples, 4, 2, 0, 0).unwrap();
            assert_eq!(samples, [3, 5, 7, 9, 3, 5, 7, 9]);
        }
    }

    #[test]
    fn png_rows_reject_invalid_layouts_and_samples() {
        for (width, height, color, palette, raw) in [
            (0, 1, 0, 0, vec![0, 1]),
            (1, 0, 0, 0, vec![0, 1]),
            (usize::MAX, 1, 6, 0, vec![0, 1]),
            (1, usize::MAX, 0, 0, vec![0, 1]),
            (1, 1, 1, 0, vec![0, 1]),
            (1, 1, 3, 0, vec![0, 1]),
            (1, 1, 3, 257, vec![0, 1]),
            (1, 1, 3, 2, vec![0, 2]),
            (1, 1, 0, 1, vec![0, 1]),
            (1, 1, 0, 0, vec![5, 1]),
            (1, 1, 0, 0, vec![0]),
            (1, 1, 0, 0, vec![0, 1, 2]),
        ] {
            assert!(png_rows(
                &mut Cursor::new(raw),
                &mut Vec::new(),
                width,
                height,
                color,
                palette
            )
            .is_err());
        }
    }

    #[test]
    fn staged_stream_copy_preserves_complete_payload() {
        let original: Vec<_> = (0..1024 * 1024).map(|i| (i % 251) as u8).collect();
        let mut input = Cursor::new(&original);
        let mut output = Vec::new();
        copy_replacement(&mut input, original.len() as u64, &mut output).unwrap();
        assert_eq!(output, original);
    }

    #[test]
    fn staged_stream_growth_and_truncation_are_rejected() {
        for length in [127, 129, 64 * 1024] {
            let mut input = Cursor::new(vec![0x42; length]);
            let mut output = Vec::new();
            assert!(copy_replacement(&mut input, 128, &mut output).is_err());
            assert!(output.len() <= 129);
        }
    }

    fn legacy_root() -> Vec<u8> {
        let mut data = vec![0; 1024];
        data[..8].copy_from_slice(&[0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
        data[26..34].copy_from_slice(&[3, 0, 0xfe, 0xff, 9, 0, 6, 0]);
        data[512] = b'R';
        data[576..579].copy_from_slice(&[2, 0, 5]);
        data[580..640].fill(0x42);
        data
    }

    #[test]
    fn root_normalization_changes_only_service_name() {
        let original = legacy_root();
        let mut normalized = original.clone();
        normalize_root_name(&mut normalized);
        assert_eq!(&normalized[..512], &original[..512]);
        assert_eq!(&normalized[578..], &original[578..]);
        let name: Vec<u8> = "Root Entry"
            .encode_utf16()
            .flat_map(u16::to_le_bytes)
            .collect();
        assert_eq!(&normalized[512..532], name.as_slice());
        assert_eq!(&normalized[576..578], &[22, 0]);
        let first = normalized.clone();
        normalize_root_name(&mut normalized);
        assert_eq!(normalized, first);
    }

    #[test]
    fn other_root_defects_are_not_repaired() {
        for (offset, value) in [(512, b'X'), (514, b'X'), (576, 3), (578, 2), (26, 4)] {
            let mut data = legacy_root();
            data[offset] = value;
            let original = data.clone();
            normalize_root_name(&mut data);
            assert_eq!(data, original);
        }
        let mut data = legacy_root();
        data[48..52].copy_from_slice(&u32::MAX.to_le_bytes());
        let original = data.clone();
        normalize_root_name(&mut data);
        assert_eq!(data, original);
    }

    #[test]
    fn replacement_scopes_are_closed() {
        for (host, name) in [
            ("doc", "WordDocument"),
            ("doc", "1Table"),
            ("xls", "Workbook"),
            ("ppt", "Current User"),
            ("hwp", "BodyText/Section2"),
            ("hwp", "BinData/BIN000B.png"),
            ("doc-object", "ObjectPool/_1269427460/Workbook"),
            ("xls-object", "MBD1234ABCD/BodyText/Section0"),
        ] {
            assert!(qualified_path(host, name), "{host}: {name}");
        }
        for (host, name) in [
            ("arbitrary", "Workbook"),
            ("doc", "ObjectPool/_1/WordDocument"),
            ("xls", "WordDocument"),
            ("hwp", "FileHeader"),
            ("hwp", "BodyText/Section"),
            ("doc-object", "ObjectPool/_1"),
            ("doc-object", "ObjectPool/other/Workbook"),
            ("xls-object", "MBDABC/Workbook"),
            ("xls-object", "MBD1234ABCD/../Workbook"),
            ("doc-object", "ObjectPool/_1/evil\\name"),
            ("doc-object", "ObjectPool/_1/evil\0name"),
            ("doc-object", "/ObjectPool/_1/Workbook"),
            ("doc-object", "ObjectPool/_1//Workbook"),
        ] {
            assert!(!qualified_path(host, name), "{host}: {name}");
        }
    }
}
