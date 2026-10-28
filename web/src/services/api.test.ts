import { describe, it, expect, vi } from "vitest";
import { api } from "./api";

describe("api fallback", () => {
  it("keeps bundled demo files when the backend only returns seeded cases", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify([
            {
              id: "DEMO-02",
              company_name: "AGRO NORD TRANS SRL",
              status: "exceptions",
              red: 1,
              amber: 1,
            },
          ]),
          { status: 200 },
        ),
      ),
    );

    const r = await api.listCases();

    expect(r.source).toBe("mixed");
    expect(r.data).toHaveLength(10);
    expect(r.data.filter((c) => c.id === "DEMO-02")).toHaveLength(1);
  });

  it("returns the 10 bundled companies when the backend is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const r = await api.listCases();
    expect(r.source).toBe("mock");
    expect(r.data).toHaveLength(10);
    expect(r.data.find((c) => c.id === "DEMO-02")?.cui).toBe("41738200");
  });
});

