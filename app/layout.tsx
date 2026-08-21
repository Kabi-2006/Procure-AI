import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title:"ProcureAI", description:"AI-assisted quotation analysis, supplier comparison, approval and purchase-order generation.", icons:{icon:"/favicon.svg",shortcut:"/favicon.svg"}, openGraph:{title:"ProcureAI",description:"From quotation to purchase order — intelligently.",images:["/og.png"]}, twitter:{card:"summary_large_image",title:"ProcureAI",description:"From quotation to purchase order — intelligently.",images:["/og.png"]} };
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><head><meta name="codex-preview" content="development" /></head><body>{children}</body></html>}
