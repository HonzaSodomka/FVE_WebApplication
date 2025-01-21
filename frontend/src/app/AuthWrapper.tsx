"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuthWrapperProps {
  children: React.ReactNode;
}

export default function AuthWrapper({ children }: AuthWrapperProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkAccess = async () => {
      if (pathname === "/password") {
        setIsLoading(false);
        return;
      }

      try {
        const response = await fetch(`${API_URL}/api/auth/check/`, {
          credentials: "include",
        });
        const data = await response.json();

        if (!data.hasAccess) {
          router.replace("/password");
        }
      } catch (error) {
        console.error("Error checking access:", error);
        router.replace("/password");
      } finally {
        setIsLoading(false);
      }
    };

    checkAccess();
  }, [pathname, router]);

  if (isLoading && pathname !== "/password") {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl">Načítání...</div>
      </div>
    );
  }

  return <>{children}</>;
}