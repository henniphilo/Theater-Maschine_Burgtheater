import "./globals.css";
import { Inter } from "next/font/google";
import { ReactNode } from "react";

import { AppShell } from "@/components/layout/AppShell";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter"
});

export const metadata = {
  title: "AutoPlay",
  description: "Dramaturgie. Automation. Performance."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de" className={inter.variable} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("autoplay-theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);document.documentElement.style.colorScheme=t;}}catch(e){}})();`
          }}
        />
      </head>
      <body className={inter.className}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
