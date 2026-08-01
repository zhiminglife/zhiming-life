import { afterEach, describe, expect, it, vi } from "vitest";

import { waitForLocalApi } from "./api";

describe("waitForLocalApi", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps waiting through a slow bundled sidecar cold start", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    for (let index = 0; index < 21; index += 1) {
      fetchMock.mockRejectedValueOnce(new TypeError("Load failed"));
    }
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 200 }));

    await waitForLocalApi("http://127.0.0.1:54321", 22, 0);

    expect(fetchMock).toHaveBeenCalledTimes(22);
    expect(fetchMock).toHaveBeenLastCalledWith("http://127.0.0.1:54321/api/health");
  });

  it("reports a clear error when the bundled sidecar never becomes ready", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Load failed"));

    await expect(waitForLocalApi("http://127.0.0.1:54321", 2, 0)).rejects.toThrow(
      "本地服务启动超时，请重新连接",
    );
  });
});
