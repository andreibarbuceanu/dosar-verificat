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

  it("keeps documents returned for a completely new backend case", async () => {
    const dynamicCase = {
      id: "C-new",
      company_name: "COMPANIE NOUĂ SRL",
      cui: "12345678",
      status: "escalated",
      documents: [
        { id: "C-new-d1", type: "application", file: "cerere.pdf", pages: 1, readable: true },
      ],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(dynamicCase), { status: 200 })),
    );

    const r = await api.getCase("C-new");

    expect(r.source).toBe("backend");
    expect(r.data?.documents).toEqual([
      expect.objectContaining({ document_id: "C-new-d1", source: "backend", file: "cerere.pdf" }),
    ]);
  });

  it("uses bundled viewable PDFs for metadata-only seeded backend cases", async () => {
    const seededCase = {
      id: "DEMO-02",
      company_name: "AGRO NORD TRANS SRL",
      cui: "41738200",
      status: "exceptions",
      documents: [
        { id: "d1", type: "application", file: "cerere_credit.pdf", pages: 2, readable: true },
      ],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(seededCase), { status: 200 })),
    );

    const r = await api.getCase("DEMO-02");

    expect(r.data?.documents).toHaveLength(5);
    expect(r.data?.documents[0]?.source).toBeUndefined();
    expect(r.data?.documents[0]?.file).toMatch(/^pdfs\/DEMO-02\/document_\d\.pdf$/);
  });

  it("returns the 10 bundled companies when the backend is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const r = await api.listCases();
    expect(r.source).toBe("mock");
    expect(r.data).toHaveLength(10);
    expect(r.data.find((c) => c.id === "DEMO-02")?.cui).toBe("41738200");
  });
});

describe("backend case integrity", () => {
  it("does not borrow planted findings or identity from a bundled company", async () => {
    const raw = {
      id: "C-real",
      company_name: "AGRO NORD TRANS SRL",
      cui: "",
      status: "running",
      documents: [],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(raw), { status: 200 })),
    );
    const result = await api.getCase(raw.id);
    expect(result.data?.findings).toEqual([]);
    expect(result.data?.cui).toBe("");
    expect(result.data?.documents).toEqual([]);
    expect(result.data?.status).toBe("running");
    expect(result.raw).toEqual(raw);
  });
  it("preserves pass, fail and unknown backend results", async () => {
    const findings = ["pass", "fail", "unknown"].map((result, index) => ({
      id: `f${index}`,
      rule_id: "R03",
      severity: "red",
      result,
      evidence: [],
      explanation: result,
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            id: "C-results",
            company_name: "Nou",
            cui: "",
            status: "exceptions",
            documents: [],
            fields: [],
            tool_results: [],
            outcome: { result: "exceptions", litigation_score: 0, findings },
          }),
          { status: 200 },
        ),
      ),
    );
    expect((await api.getCase("C-results")).data?.findings).toEqual(findings);
  });
});
