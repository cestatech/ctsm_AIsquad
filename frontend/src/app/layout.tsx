import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Celerius",
  description: "Clinical Trial Lifecycle Platform",
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
