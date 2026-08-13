import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FeedbackControls } from "@/features/recommendations/feedback-controls";

describe("FeedbackControls", () => {
  it("submits a complete accessible half-step feedback resource", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();

    render(
      <FeedbackControls
        gameId={7}
        gameTitle="Signal Frontier"
        pending={false}
        onSave={onSave}
        onClear={vi.fn()}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Reaction"), "liked");
    await user.selectOptions(screen.getByLabelText("Rating"), "8.5");
    await user.click(screen.getByRole("checkbox", { name: "Played" }));
    await user.click(screen.getByRole("checkbox", { name: "Wishlist" }));
    await user.click(screen.getByRole("button", { name: "Save feedback" }));

    expect(onSave).toHaveBeenCalledWith(7, {
      reaction: "liked",
      played: true,
      wishlisted: true,
      rating: 8.5,
    });
  });

  it("rehydrates saved state and exposes pending and clear behavior", async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    const { rerender } = render(
      <FeedbackControls
        gameId={7}
        gameTitle="Signal Frontier"
        pending={false}
        saved={{
          game_id: 7,
          game_slug: "signal-frontier",
          game_title: "Signal Frontier",
          reaction: "disliked",
          played: false,
          wishlisted: true,
          rating: 4.5,
          latest_occurred_at: "2026-08-12T00:00:00Z",
        }}
        onSave={vi.fn()}
        onClear={onClear}
      />,
    );

    expect(screen.getByLabelText("Reaction")).toHaveValue("disliked");
    expect(screen.getByLabelText("Rating")).toHaveValue("4.5");
    expect(screen.getByRole("checkbox", { name: "Wishlist" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Clear feedback" }));
    expect(onClear).toHaveBeenCalledWith(7);

    rerender(
      <FeedbackControls
        gameId={7}
        gameTitle="Signal Frontier"
        pending
        message="Saving feedback…"
        onSave={vi.fn()}
        onClear={onClear}
      />,
    );
    expect(
      screen.getByRole("group", { name: "Feedback for Signal Frontier" }),
    ).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("Saving feedback…");
  });
});
