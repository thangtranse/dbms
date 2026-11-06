import type { Metadata } from "next";
import { Be_Vietnam_Pro, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { BuildVersion } from "@/components/build-version";

const body = Be_Vietnam_Pro({ subsets: ["vietnamese", "latin"], weight: ["400", "500", "600", "700"], variable: "--font-body" });
const mono = JetBrains_Mono({ subsets: ["vietnamese", "latin"], weight: ["400", "500"], variable: "--font-mono-face" });

export const metadata: Metadata = {
  title: "OfficeLunch — Hôm nay ăn gì?",
  description: "Gợi ý món ăn trưa theo ngữ cảnh cho dân văn phòng",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body className={`${body.variable} ${mono.variable} antialiased`}><BuildVersion />{children}</body>
    </html>
  );
}
