import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Trendbox',
  description: 'Created by PNJ Team',
  authors: [{ name: 'PNJ Team' }],
  creator: 'PNJ Team',
  publisher: 'PNJ Team',
  generator: 'PNJ Team',
  openGraph: {
    title: 'Trendbox',
    description: 'Created by PNJ Team',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
