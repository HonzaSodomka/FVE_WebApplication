import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Získání stavu přihlášení
  const isAuthenticated = request.cookies.get('is_authenticated')?.value === 'true';

  // Pokud jsme na /login a jsme přihlášení, přesměruj na dashboard
  if (request.nextUrl.pathname === '/login' && isAuthenticated) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  // Pokud nejsme na /login a nejsme přihlášení, přesměruj na login
  if (request.nextUrl.pathname !== '/login' && !isAuthenticated) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)']
};