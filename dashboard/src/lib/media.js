// Archive-first photo URL for complaint evidence.
//
// When the API runs with MEDIA_ROOT set (Railway volume), every photo is copied
// to the server disk and served from /v2/complaints/:id/images/:kind with the
// usual JWT. Rows created before the volume existed only carry a Telegram
// file_id, which the legacy /image/:file_id proxy still streams.
export function imageSrc(image) {
  if (!image) return null;
  if (image.stored && image.url) return image.url;
  if (image.telegram_file_id) return `/image/${image.telegram_file_id}`;
  return null;
}

export function imageFor(images, kind) {
  if (!Array.isArray(images)) return null;
  return images.find((image) => image.kind === kind) || null;
}
