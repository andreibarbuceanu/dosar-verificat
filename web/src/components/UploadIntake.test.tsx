import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { UploadIntake } from "./UploadIntake";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("UploadIntake", () => {
  it("uploads, processes, and returns the real case id", async () => {
    const payload = {
      id: "C-real",
      company_name: "",
      cui: "",
      status: "new",
      documents: [],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(payload), { status: 201 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ...payload, status: "running" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const complete = vi.fn();
    render(<UploadIntake onComplete={complete} />);
    fireEvent.change(screen.getByLabelText(/trage pdf-urile aici/i), {
      target: { files: [new File(["pdf"], "document.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() => expect(complete).toHaveBeenCalledWith("C-real"));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows backend processing errors", async () => {
    const payload = {
      id: "C-bad",
      company_name: "",
      cui: "",
      status: "new",
      documents: [],
      fields: [],
      tool_results: [],
      outcome: null,
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response(JSON.stringify(payload), { status: 201 }))
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: "PDF could not be processed" }), { status: 422 }),
        ),
    );
    render(<UploadIntake onComplete={vi.fn()} />);
    fireEvent.change(screen.getByLabelText(/trage pdf-urile aici/i), {
      target: { files: [new File(["pdf"], "document.pdf", { type: "application/pdf" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("PDF could not be processed");
  });
});
