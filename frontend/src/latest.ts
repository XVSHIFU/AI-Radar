export function latestRequest() {
  let generation = 0;
  let controller: AbortController | undefined;
  return {
    begin() {
      controller?.abort();
      controller = new AbortController();
      const id = ++generation;
      return {
        id,
        signal: controller.signal,
        current: () => id === generation,
      };
    },
    cancel() {
      controller?.abort();
      generation++;
    },
  };
}
