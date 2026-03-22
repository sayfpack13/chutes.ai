/* global window */
/**
 * Read a POST response as newline-delimited JSON from the build/deploy NDJSON stream endpoints.
 */
async function consumeChutesNdjsonStream(url, handlers) {
  const onLog = handlers && handlers.onLog;
  const onResult = handlers && handlers.onResult;
  const onHttpError = handlers && handlers.onHttpError;

  const res = await fetch(url, { method: "POST" });
  if (!res.ok || !res.body) {
    const text = await res.text();
    if (onHttpError) onHttpError(res.status, text);
    return {
      httpOk: false,
      ok: false,
      data: {
        ok: false,
        returncode: res.status,
        stdout: "",
        stderr: text.slice(0, 8000),
      },
    };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let lastResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      let ev;
      try {
        ev = JSON.parse(line);
      } catch {
        if (onLog) onLog(line);
        continue;
      }
      if (ev.type === "log" && onLog) onLog(ev.message);
      if (ev.type === "result") {
        lastResult = ev;
        if (onResult) onResult(ev);
      }
    }
  }

  const data = lastResult
    ? {
        ok: !!lastResult.ok,
        returncode: lastResult.returncode,
        stdout: lastResult.stdout || "",
        stderr: lastResult.stderr || "",
        ref: lastResult.ref,
      }
    : { ok: false, returncode: -1, stdout: "", stderr: "Stream ended without a result." };

  return { httpOk: true, ok: !!data.ok, data };
}

window.consumeChutesNdjsonStream = consumeChutesNdjsonStream;
