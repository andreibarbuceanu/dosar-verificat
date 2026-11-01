import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DocumentEvidence } from "./DocumentEvidence";
afterEach(cleanup);
const document = { id: "C-real-d1", type: "bilant", file: "bilant.pdf", pages: 2, readable: true };
const fields = [
  {
    id: "f1",
    name: "turnover",
    value: 12400000,
    doc_id: document.id,
    page: 2,
    quote: "Cifra de afaceri: 12.400.000",
    verified: true,
  },
];
describe("backend document evidence", () => {
  it("brings single-page evidence into view on every click, even when the page is unchanged", () => {
    render(
      <DocumentEvidence
        document={{ ...document, pages: 1 }}
        fields={[{ ...fields[0]!, page: 1 }]}
      />,
    );
    const viewer = screen.getByRole("region", { name: "Previzualizare dovadă PDF" });
    const scroll = vi.fn();
    viewer.scrollIntoView = scroll;
    const button = screen.getByRole("button", { name: "Vezi dovada" });
    fireEvent.click(button);
    expect(viewer).toHaveFocus();
    expect(scroll).toHaveBeenCalledWith({ behavior: "auto", block: "start" });
    fireEvent.click(button);
    expect(scroll).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("img")).toHaveAttribute("src", expect.stringContaining("/pages/1"));
  });
  it("opens the quoted page and bounds navigation", () => {
    render(<DocumentEvidence document={document} fields={fields} />);
    expect(screen.getByText(/Cifra de afaceri: 12.400.000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Vezi dovada" }));
    expect(screen.getByRole("img")).toHaveAttribute(
      "src",
      expect.stringContaining("/documents/C-real-d1/pages/2"),
    );
    expect(screen.getByRole("button", { name: "Următor" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Anterior" }));
    expect(screen.getByRole("img")).toHaveAttribute("src", expect.stringContaining("/pages/1"));
  });
  it("reports unavailable pages and retries on a different page", () => {
    render(<DocumentEvidence document={document} fields={[]} />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByRole("status")).toHaveTextContent("Pagina nu este disponibilă");
    fireEvent.click(screen.getByRole("button", { name: "Următor" }));
    expect(screen.getByRole("img")).toHaveAttribute("src", expect.stringContaining("/pages/2"));
  });
});
