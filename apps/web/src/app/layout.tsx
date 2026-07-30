import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("http://localhost:3000"),
  title: {
    default: "GameLens AI · Catalog lab",
    template: "%s · GameLens AI",
  },
  description:
    "Explore a transparent game catalog while GameLens AI's recommendation system is built in public.",
  openGraph: {
    title: "GameLens AI · Catalog lab",
    description:
      "Browse a transparent game catalog today. Recommendation intelligence arrives in a later stage.",
    type: "website",
    images: [
      {
        url: "/images/gamelens-social-preview.webp",
        width: 1200,
        height: 630,
        alt: "Abstract GameLens AI archive cards and orbital lens illustration",
      },
    ],
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <div className="site-frame">
          <SiteHeader />
          <main id="main-content" tabIndex={-1}>
            {children}
          </main>
          <SiteFooter />
        </div>
      </body>
    </html>
  );
}
