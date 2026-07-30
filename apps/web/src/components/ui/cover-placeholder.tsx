import type { CSSProperties } from "react";

interface CoverPlaceholderProps {
  gameId: number;
  title: string;
  variant?: "card" | "detail";
}

type CoverStyle = CSSProperties & { "--cover-hue": number };

export function CoverPlaceholder({
  gameId,
  title,
  variant = "card",
}: CoverPlaceholderProps) {
  const initials = title
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  const style: CoverStyle = { "--cover-hue": (gameId * 47) % 360 };

  return (
    <div
      className={`cover-placeholder cover-placeholder--${variant}`}
      style={style}
      role="img"
      aria-label={`Placeholder cover for ${title}`}
    >
      <span className="cover-placeholder__grid" aria-hidden="true" />
      <span className="cover-placeholder__index" aria-hidden="true">
        GL-{String(gameId).padStart(3, "0")}
      </span>
      <span className="cover-placeholder__initials" aria-hidden="true">
        {initials}
      </span>
      <span className="cover-placeholder__label" aria-hidden="true">
        Archive edition
      </span>
    </div>
  );
}
