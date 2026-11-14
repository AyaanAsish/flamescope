import type { Metadata } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

const inter = localFont({
  src: "../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = localFont({
  src: "../node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2",
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "FlameScope", template: "%s | FlameScope" },
  description:
    "Combustion investigations from NASA PSI, summarized, ranked and interpreted for fire safety.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
