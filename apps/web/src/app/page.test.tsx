import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { metadata as rootMetadata } from "@/app/layout";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("presents the active catalog and recommendation routes truthfully", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Find your next world/ }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /Explore the catalog/ })).toHaveAttribute(
      "href",
      "/games",
    );
    expect(screen.getByText("Content TF-IDF")).toBeVisible();
    expect(screen.getByText("Seed games")).toBeVisible();
    expect(screen.queryByText(/catalog online|live now/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Build a shortlist/i })).toHaveAttribute(
      "href",
      "/recommendations",
    );
    expect(String(rootMetadata.description)).toMatch(/explained.*recommendations/i);
    expect(String(rootMetadata.openGraph?.description)).not.toMatch(
      /arrives in a later stage/i,
    );
  });
});
