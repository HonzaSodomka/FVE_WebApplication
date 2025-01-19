import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const isAuthenticated = request.cookies.get('is_authenticated')?.value === 'true';

  // Chráněné cesty které vyžadují přihlášení
  const protectedPaths = ['/dashboard'];

  // Je aktuální cesta chráněná?
  const isProtectedPath = protectedPaths.some(path => 
    request.nextUrl.pathname.startsWith(path)
  );

  // Pokud přistupujeme na chráněnou cestu a nejsme přihlášení
  if (isProtectedPath && !isAuthenticated) {
    const loginUrl = new URL('/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  // Pokud jsme na login stránce a jsme přihlášení
  if (request.nextUrl.pathname === '/login' && isAuthenticated) {
    const dashboardUrl = new URL('/dashboard', request.url);
    return NextResponse.redirect(dashboardUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/login']
};