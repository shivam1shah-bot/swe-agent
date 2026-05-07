import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api";

interface User {
  email: string;
  username?: string;
  role?: string;
  picture?: string;
}

export function useCurrentUser() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const token = localStorage.getItem("auth_token");
        if (!token) {
          setUser(null);
          setIsLoading(false);
          return;
        }

        const userData = await apiClient.getCurrentUser();
        setUser({
          email: userData.email || userData.username || "",
          username: userData.username,
          role: userData.role,
        });
      } catch (err) {
        setError(err instanceof Error ? err : new Error("Failed to fetch user"));
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchUser();
  }, []);

  return { user, isLoading, error };
}
