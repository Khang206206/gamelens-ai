import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import HomePage from "@/app/page";

describe("HomePage", () => {
  it("presents the working catalog without claiming active recommendations", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Find your next world/ }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /Explore the catalog/ })).toHaveAttribute(
      "href",
      "/games",
    );
    expect(screen.getByText("Catalog only")).toBeVisible();
    expect(screen.getByText("Seed games")).toBeVisible();
    expect(screen.queryByText(/catalog online|live now/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /recommend/i })).not.toBeInTheDocument();
  });
});
