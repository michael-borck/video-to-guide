export async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = typeof data?.detail === "string" ? data.detail : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  return response.json();
}

export function mediaUrl(project, path) {
  return `/media/${encodeURIComponent(project)}/${path.split("/").map(encodeURIComponent).join("/")}`;
}

export function createSaveQueue(save, onStatus = () => {}) {
  let tail = Promise.resolve();
  let pending = 0;
  let error = null;
  return {
    enqueue(guide) {
      // A later complete snapshot can recover from a failed earlier save.
      const snapshot = structuredClone(guide);
      const operation = tail.catch(() => {}).then(() => save(snapshot));
      tail = operation;
      pending += 1;
      onStatus({ pending, error });
      operation.then(
        () => {
          pending -= 1;
          error = null;
          onStatus({ pending, error });
        },
        (failure) => {
          pending -= 1;
          error = failure.message;
          onStatus({ pending, error });
        }
      );
      return operation;
    },
    async flush() {
      // Include saves added while an earlier request was in flight.
      let current;
      do {
        current = tail;
        try {
          await current;
        } catch (error) {
          if (current === tail) throw error;
        }
      } while (current !== tail);
    },
  };
}
