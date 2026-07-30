import Link from "next/link";

import { StateNotice } from "@/components/ui/state-notice";

export default function InvalidGameId() {
  return (
    <div className="detail-page shell">
      <StateNotice
        eyebrow="Invalid game address"
        title="This game identifier is not valid."
        description="Game addresses use a positive whole number. No catalog request was sent."
        headingLevel={1}
        tone="warning"
        action={
          <Link className="button button--primary" href="/games">
            Return to the catalog
          </Link>
        }
      />
    </div>
  );
}
