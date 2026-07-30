import type { ReactNode } from "react";

interface StateNoticeProps {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
  headingLevel?: 1 | 2;
  tone?: "default" | "warning";
  live?: boolean;
}

export function StateNotice({
  eyebrow,
  title,
  description,
  action,
  headingLevel = 2,
  tone = "default",
  live = false,
}: StateNoticeProps) {
  const Heading = headingLevel === 1 ? "h1" : "h2";

  return (
    <section
      className={`state-notice state-notice--${tone}`}
      aria-live={live ? "polite" : undefined}
    >
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <Heading>{title}</Heading>
      <p>{description}</p>
      {action ? <div className="state-notice__action">{action}</div> : null}
    </section>
  );
}
