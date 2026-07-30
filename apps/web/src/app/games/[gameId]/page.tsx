import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { GameDetailView } from "@/features/game-detail/game-detail-view";
import { parseGameId } from "@/lib/routes";

export const metadata: Metadata = {
  title: "Game details",
  description: "Inspect one title from the GameLens AI development catalog.",
};

export default async function GameDetailPage({
  params,
}: {
  params: Promise<{ gameId: string }>;
}) {
  const { gameId } = await params;
  if (parseGameId(gameId) === null) notFound();

  return (
    <div className="detail-page shell">
      <GameDetailView rawGameId={gameId} />
    </div>
  );
}
