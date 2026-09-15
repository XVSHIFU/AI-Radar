/** Prefer DeepSeek's Chinese news page while retaining the stored source URL. */
export function preferredReadingUrl(sourceUrl: string, language: "zh" | "en" = "zh"): string {
  if (language === "en") return sourceUrl;
  try {
    const url = new URL(sourceUrl);
    if (url.hostname === "api-docs.deepseek.com" && /^\/news\/news\d+\/?$/.test(url.pathname)) { url.pathname = `/zh-cn${url.pathname}`; return url.toString(); }
  } catch { /* caller validates the original link */ }
  return sourceUrl;
}
