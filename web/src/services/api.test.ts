import { describe, it, expect, vi } from "vitest";
import { api } from "./api";

describe("api fallback", () => {
  it("returns the 10 bundled companies when the backend is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const r = await api.listCases();
    expect(r.source).toBe("mock");
    expect(r.data).toHaveLength(10);
    expect(r.data.find((c) => c.id === "DEMO-02")?.cui).toBe("41738200");
  });
});

