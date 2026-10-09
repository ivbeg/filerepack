/* Development-only Apache POI 5.4.1 animation/image/save/reopen control. */
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.*;
import javax.imageio.ImageIO;
import org.apache.poi.ddf.*;
import org.apache.poi.hslf.record.*;
import org.apache.poi.hslf.usermodel.*;

public class PptAnimationCompatibility {
    static String hash(byte[] data) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
    }
    static void animationRecords(org.apache.poi.hslf.record.Record[] records,
                                 List<String> result) throws Exception {
        for (org.apache.poi.hslf.record.Record record : records) {
            long kind = record.getRecordType();
            if (kind == 4081 || kind == 4116 || kind == 5000 || kind == 5003) {
                ByteArrayOutputStream raw = new ByteArrayOutputStream();
                record.writeOut(raw);
                result.add(kind + ":" + hash(raw.toByteArray()));
            }
            org.apache.poi.hslf.record.Record[] children = record.getChildRecords();
            if (children != null) animationRecords(children, result);
            if (record instanceof PPDrawing drawing) clientData(drawing.getEscherRecords(), result);
        }
    }
    static void clientData(List<EscherRecord> records, List<String> result) throws Exception {
        for (EscherRecord record : records) {
            if (record instanceof EscherClientDataRecord)
                result.add("shape_client_data:" + hash(record.serialize()));
            clientData(record.getChildRecords(), result);
        }
    }
    static String picture(HSLFPictureData picture) throws Exception {
        byte[] data = picture.getData();
        BufferedImage image = ImageIO.read(new ByteArrayInputStream(data));
        if (image == null) return picture.getType() + ":raw:" + hash(data);
        int width = image.getWidth(), height = image.getHeight();
        ByteBuffer pixels = ByteBuffer.allocate(width * height * 4);
        for (int y = 0; y < height; y++)
            for (int x = 0; x < width; x++) pixels.putInt(image.getRGB(x, y));
        return picture.getType() + ":" + width + "x" + height + ":" + hash(pixels.array());
    }
    static Map<String, Object> snapshot(HSLFSlideShow show) throws Exception {
        Map<String, Object> result = new TreeMap<>();
        result.put("slides", show.getSlides().size());
        result.put("masters", show.getSlideMasters().size());
        result.put("notes", show.getNotes().size());
        List<String> records = new ArrayList<>();
        animationRecords(show.getSlideShowImpl().getRecords(), records);
        result.put("animation_and_tag_records", records);
        List<String> pictures = new ArrayList<>();
        for (HSLFPictureData picture : show.getPictureData()) pictures.add(picture(picture));
        result.put("pictures", pictures);
        Map<Integer, String> storages = new TreeMap<>();
        for (HSLFObjectData storage : show.getEmbeddedObjects()) {
            try (InputStream input = storage.getInputStream()) {
                storages.put(storage.getExOleObjStg().getPersistId(), hash(input.readAllBytes()));
            }
        }
        result.put("storages", storages);
        int resolved = 0;
        ExObjList objects = show.getDocumentRecord().getExObjList(false);
        if (objects != null) {
            for (org.apache.poi.hslf.record.Record record : objects.getChildRecords()) {
                if (record instanceof ExEmbed embed &&
                    storages.containsKey(embed.getExOleObjAtom().getObjStgDataRef())) resolved++;
            }
        }
        result.put("resolved", resolved);
        return result;
    }
    static Map<String, Object> inspectAndSave(String input, String output) throws Exception {
        try (HSLFSlideShow show = new HSLFSlideShow(new FileInputStream(input))) {
            Map<String, Object> before = snapshot(show);
            try (OutputStream destination = new FileOutputStream(output)) { show.write(destination); }
            try (HSLFSlideShow saved = new HSLFSlideShow(new FileInputStream(output))) {
                if (!before.equals(snapshot(saved)))
                    throw new IllegalStateException("Content differs after save/reopen: " + input);
            }
            System.out.println("file=" + new File(input).getName() + " slides=" + before.get("slides")
                + " masters=" + before.get("masters") + " notes=" + before.get("notes")
                + " pictures=" + ((List<?>) before.get("pictures")).size()
                + " animation_and_tag_records=" + ((List<?>) before.get("animation_and_tag_records")).size()
                + " tag_lists=" + ((List<?>) before.get("animation_and_tag_records")).stream()
                    .filter(item -> item.toString().startsWith("5000:")).count()
                + " shape_client_data=" + ((List<?>) before.get("animation_and_tag_records")).stream()
                    .filter(item -> item.toString().startsWith("shape_client_data:")).count()
                + " storages=" + ((Map<?, ?>) before.get("storages")).size()
                + " resolved=" + before.get("resolved") + " save_reopen_equal=true");
            return before;
        }
    }
    public static void main(String[] args) throws Exception {
        Map<String, Object> source = inspectAndSave(args[0], args[2]);
        Map<String, Object> candidate = inspectAndSave(args[1], args[3]);
        if (!source.equals(candidate)) throw new IllegalStateException("Source/candidate content differs");
        System.out.println("source_candidate_equal=true decoded_pixels_animation_tags_and_embeddings=true");
    }
}
