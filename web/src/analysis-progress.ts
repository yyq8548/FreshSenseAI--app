export function analysisProgressMessage(elapsedSeconds: number): string {
  if (elapsedSeconds < 5) {
    return "Uploading the photo and running the fast visual scan...";
  }
  if (elapsedSeconds < 15) {
    return "The service is still processing this scan. A recently started server can take a little longer.";
  }
  return "Still working. Keep this page open and do not submit the photo twice. If this continues, the service may be starting after an idle period.";
}
