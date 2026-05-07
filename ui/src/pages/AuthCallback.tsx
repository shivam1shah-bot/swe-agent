import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

export const AuthCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const token = searchParams.get('token');
    
    if (token) {
      // Store token and redirect to home
      localStorage.setItem('auth_token', token);
      
      // Clear Basic Auth if present to prevent conflict
      localStorage.removeItem('basic_auth_creds');
      
      // Configure API client (if you have a global config function)
      // or rely on the interceptor to pick up the token
      
      navigate('/');
    } else {
      // Handle error
      navigate('/login?error=auth_failed');
    }
  }, [searchParams, navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-slate-900">
      <Card className="w-[400px] shadow-lg">
        <CardHeader className="text-center">
          <CardTitle>Authenticating...</CardTitle>
        </CardHeader>
        <CardContent className="flex justify-center p-8">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </CardContent>
      </Card>
    </div>
  );
};

