const MAX_ANALYSIS_DIMENSION = 1024;
const PASSTHROUGH_BYTES = 1024 * 1024;

/**
 * Shrink phone photos before upload. The vision model ultimately consumes a
 * 224px tensor, so multi-megapixel uploads add latency without adding usable
 * inference detail.
 */
export async function prepareAnalysisImage(file: File): Promise<File> {
  const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  try {
    const scale = Math.min(
      1,
      MAX_ANALYSIS_DIMENSION / Math.max(bitmap.width, bitmap.height),
    );
    if (scale === 1 && file.size <= PASSTHROUGH_BYTES) {
      return file;
    }

    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) {
      return file;
    }
    context.drawImage(bitmap, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", 0.86);
    });
    if (!blob || blob.size >= file.size) {
      return file;
    }
    const stem = file.name.replace(/\.[^.]+$/, "") || "fruit";
    return new File([blob], `${stem}-analysis.jpg`, {
      type: "image/jpeg",
      lastModified: file.lastModified,
    });
  } finally {
    bitmap.close();
  }
}
