/* Development-only Apache POI 5.4.1 reader/editing control; never a runtime writer. */
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import org.apache.poi.hslf.usermodel.*;
import org.apache.poi.hslf.record.*;
import org.apache.poi.poifs.filesystem.*;

public class PptStorageCompatibility {
    static String hash(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    static Map<Integer, String> payloads(HSLFSlideShow show) throws Exception {
        Map<Integer, String> hashes = new TreeMap<>();
        for (HSLFObjectData data : show.getEmbeddedObjects()) {
            try (InputStream input = data.getInputStream()) {
                hashes.put(data.getExOleObjStg().getPersistId(), hash(input.readAllBytes()));
            }
        }
        return hashes;
    }
    static int resolved(HSLFSlideShow show, Map<Integer, String> hashes) {
        int count = 0;
        for (org.apache.poi.hslf.record.Record record :
                show.getDocumentRecord().getExObjList(false).getChildRecords()) {
            if (record instanceof ExEmbed embed) {
                if (hashes.containsKey(embed.getExOleObjAtom().getObjStgDataRef())) count++;
            }
        }
        return count;
    }
    static void inspect(String path) throws Exception {
        try (HSLFSlideShow show = new HSLFSlideShow(new FileInputStream(path))) {
            Map<Integer, String> hashes = payloads(show);
            System.out.println("file=" + new File(path).getName() + " slides=" + show.getSlides().size()
                + " masters=" + show.getSlideMasters().size() + " storages=" + hashes.size()
                + " resolved=" + resolved(show, hashes) + " payloads=" + hashes);
        }
    }
    public static void main(String[] args) throws Exception {
        inspect(args[0]);
        if (args.length == 1) return;
        try (HSLFSlideShow show = new HSLFSlideShow(new FileInputStream(args[0]))) {
            Map<Integer, String> before = payloads(show);
            try (OutputStream out = new FileOutputStream(args[1])) { show.write(out); }
            if (args.length == 2) { inspect(args[1]); return; }
            if (before.size() != 7 || resolved(show, before) != 7)
                throw new IllegalStateException("Missing logical embedding before edit");
            HSLFObjectData selected = Arrays.stream(show.getEmbeddedObjects())
                .filter(data -> data.getExOleObjStg().getPersistId() == 3).findFirst().orElseThrow();
            byte[] updated;
            try (InputStream input = selected.getInputStream();
                 POIFSFileSystem ole = new POIFSFileSystem(input);
                 DocumentInputStream contents = ole.createDocumentInputStream("CONTENTS")) {
                byte[] image = contents.readAllBytes();
                image[image.length - 1] ^= 1;
                ole.getRoot().createOrUpdateDocument("CONTENTS", new ByteArrayInputStream(image));
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                ole.writeFilesystem(output);
                updated = output.toByteArray();
            }
            selected.setData(updated);
            try (OutputStream out = new FileOutputStream(args[2])) { show.write(out); }
            try (HSLFSlideShow edited = new HSLFSlideShow(new FileInputStream(args[2]))) {
                Map<Integer, String> after = payloads(edited);
                if (!after.keySet().equals(before.keySet()) || resolved(edited, after) != 7)
                    throw new IllegalStateException("Logical IDs lost after edit");
                for (int id : before.keySet()) {
                    if (before.get(id).equals(after.get(id)) == (id == 3))
                        throw new IllegalStateException("Wrong embedding changed: " + id);
                }
                System.out.println("independent_edit=true changed_persist=3 unchanged_other_payloads=6");
            }
            inspect(args[1]);
            inspect(args[2]);
        }
    }
}
