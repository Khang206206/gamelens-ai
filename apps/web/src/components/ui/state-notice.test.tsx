import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StateNotice } from "@/components/ui/state-notice";

describe("StateNotice", () => {
  it("uses a section heading by default", () => {
    render(<StateNotice title="Filtered empty" description="Try another filter." />);

    expect(
      screen.getByRole("heading", { level: 2, name: "Filtered empty" }),
    ).toBeVisible();
  });

  it("can provide the page heading for full-route states", () => {
    render(
      <StateNotice
        title="This route is unavailable"
        description="Return to the catalog."
        headingLevel={1}
      />,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "This route is unavailable" }),
    ).toBeVisible();
  });
});
