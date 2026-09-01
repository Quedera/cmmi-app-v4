import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QUEDERA Pulse — ITSM Maturity Assessment",
  description:
    "ITSM capability maturity assessment. Measure, evidence, and prioritise the disciplines that matter to your service operation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}