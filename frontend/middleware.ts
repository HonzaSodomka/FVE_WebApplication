import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
 
export async function middleware(request: NextRequest) {
  // Ignore auth check for password page and static files
  if (request.nextUrl.pathname === '/password') {
    return NextResponse.next()
  }

  try {
    // Kontrola přístupu na backendu
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const response = await fetch(`${API_URL}/api/auth/check/`, {
      headers: {
        Cookie: request.headers.get('cookie') || ''
      },
    })
    
    const data = await response.json()

    // Přesměrování na password stránku pokud nemáme přístup
    if (!data.hasAccess) {
      return NextResponse.redirect(new URL('/password', request.url))
    }

    return NextResponse.next()
  } catch (error) {
    // Při chybě také přesměrujeme na password stránku
    return NextResponse.redirect(new URL('/password', request.url))
  }
}
 
// Nastavení, na které cesty se middleware vztahuje
export const config = {
  matcher: [
    /*
     * Match all paths except for:
     * 1. /password (auth page)
     * 2. /api (API routes)
     * 3. /_next (Next.js internals)
     * 4. /static (static files)
     * 5. /_vercel (Vercel internals)
     * 6. /favicon.ico, /sitemap.xml (public files)
     */
    '/((?!password|api|_next|_vercel|static|favicon.ico|sitemap.xml).*)',
  ],
}