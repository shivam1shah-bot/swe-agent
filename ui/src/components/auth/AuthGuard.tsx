import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { apiClient } from '@/lib/api';

interface AuthGuardProps {
  children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const locationRef = useRef(location);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;

    const logoutAndRedirect = () => {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('basic_auth_creds');
      if (!cancelled) {
        setIsAuthenticated(false);
        navigate('/login', { state: { from: locationRef.current } });
      }
    };

    const checkAuth = async () => {
      try {
        // If auth is disabled, allow without token
        const status = await apiClient.getAuthStatus();
        if (status?.auth_enabled === false) {
          if (!cancelled) {
            setIsAuthenticated(true);
          }
          return;
        }

        const token = localStorage.getItem('auth_token');
        if (!token) {
          logoutAndRedirect();
          return;
        }

        // Lightweight auth ping to validate token (handles expiry)
        await apiClient.getAuthMe();
        if (!cancelled) {
          setIsAuthenticated(true);
        }
      } catch (error) {
        // Auth errors (401) must always redirect to login regardless of token presence.
        // Only treat the failure as transient (e.g. network blip) when it is NOT an
        // auth error and a token is still in storage.
        const isAuthError = error instanceof Error && error.message.includes('Unauthorized');
        const token = localStorage.getItem('auth_token');
        if (token && !isAuthError) {
          if (!cancelled) {
            setIsAuthenticated(true);
          }
          return;
        }
        logoutAndRedirect();
      }
    };

    checkAuth();

    const onFocus = () => checkAuth();
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        checkAuth();
      }
    };

    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      cancelled = true;
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [navigate]);  

  // Show nothing while checking authentication status
  if (isAuthenticated === null) {
    return null; // Or a loading spinner
  }

  // If authenticated, render children
  return isAuthenticated ? <>{children}</> : null;
};

