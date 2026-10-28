import { afterEach, describe, expect, it, vi } from "vitest";
import { documentPageUrl, getCase, listCases, runCase, uploadCase } from "./index";

afterEach(() => vi.unstubAllGlobals());

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("FastAPI client", () => {
  it("loads the case list from the backend", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        response([{ id: "C-1", company_name: "ACME", status: "running", red: 0, amber: 0 }]),
      );
    vi.stubGlobal("fetch", fetchMock);
    await expect(listCases()).resolves.toEqual([
      expect.objectContaining({ id: "C-1", company_name: "ACME" }),
    ]);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/cases", undefined);
  });

  it("uploads PDFs as multipart data without setting a synthetic outcome", async () => {
    const created = {
      id: "C-new",
      company_name: "",
      cui: "",
      status: "new",
      documents: [],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(response(created, 201));
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["pdf"], "application.pdf", { type: "application/pdf" });
    await expect(uploadCase([file])).resolves.toEqual(created);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).getAll("files")).toHaveLength(1);
    expect(init.headers).toBeUndefined();
  });

  it("triggers processing and returns backend errors", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ id: "C-1", status: "running" }))
      .mockResolvedValueOnce(response({ detail: "Extraction service unavailable" }, 503));
    vi.stubGlobal("fetch", fetchMock);
    await runCase("C-1");
    await expect(getCase("missing")).rejects.toThrow("Extraction service unavailable");
    expect(fetchMock.mock.calls[0]![1]).toEqual({ method: "POST" });
  });

  it("builds a backend evidence-page URL", () => {
    expect(documentPageUrl("doc 1", 2)).toBe("http://localhost:8000/documents/doc%201/pages/2");
  });
});
