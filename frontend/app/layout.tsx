import type { Metadata, Viewport } from "next";
import { TabBar } from "@/components/TabBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "FINN — Financial Investment Agent",
  description: "Push what matters. Pull grounded research. Built for a daily investor's workflow.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "FINN" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#09090b" },
    { media: "(prefers-color-scheme: light)", color: "#f4f4f5" },
  ],
};

const themeInit = `(function(){try{var t=localStorage.getItem('finn-theme');if(t==='light'){document.documentElement.classList.remove('dark');}else{document.documentElement.classList.add('dark');}}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body className="min-h-dvh pb-20">
        {children}
        <TabBar />
      </body>
    </html>
  );
}
