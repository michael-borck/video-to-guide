import { describe, expect, it, vi } from "vitest";
import { createSaveQueue, requestJson } from "./api.js";

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

describe("ordered persistence", () => {
  it("waits for each save and includes later edits when flushing", async () => {
    const first = deferred();
    const second = deferred();
    const save = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const queue = createSaveQueue(save);
    queue.enqueue({ title: "first" });
    const finished = vi.fn();
    const flush = queue.flush().then(finished);
    queue.enqueue({ title: "second" });
    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    first.resolve();
    await vi.waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    expect(finished).not.toHaveBeenCalled();
    expect(save.mock.calls.map(([guide]) => guide.title)).toEqual(["first", "second"]);
    second.resolve();
    await flush;
    expect(finished).toHaveBeenCalledOnce();
  });

  it("blocks flush on a failed save and permits a retry", async () => {
    const status = vi.fn();
    const save = vi.fn().mockRejectedValueOnce(new Error("disk full")).mockResolvedValueOnce({});
    const queue = createSaveQueue(save, status);
    await expect(queue.enqueue({ title: "keep my edits" })).rejects.toThrow("disk full");
    await expect(queue.flush()).rejects.toThrow("disk full");
    expect(status).toHaveBeenLastCalledWith({ pending: 0, error: "disk full" });
    await queue.enqueue({ title: "keep my edits" });
    await queue.flush();
    expect(status).toHaveBeenLastCalledWith({ pending: 0, error: null });
  });

  it("rejects HTTP errors instead of treating them as saved", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "disk full" }), { status: 500 })));
    try {
      await expect(requestJson("/guide")).rejects.toThrow("disk full");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
