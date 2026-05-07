/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useEffect, useState, useRef } from 'react';
import { apiClient } from '@/lib/api';

const GoogleAuthCallback: React.FC = () => {
  const [status, setStatus] = useState<'processing' | 'success' | 'error'>('processing');
  const [message, setMessage] = useState('Processing authorization...');
  const [isProcessing, setIsProcessing] = useState(false);
  const hasProcessed = useRef(false);

  useEffect(() => {
    const processAuth = async () => {
      // Prevent duplicate processing using ref
      if (hasProcessed.current || isProcessing) {
        return;
      }
      
      // Check if already processed by looking at session storage
      const existingParsedData = sessionStorage.getItem('parsedGoogleDocData');
      if (existingParsedData) {
        setStatus('success');
        setMessage('Google Doc already processed. Redirecting...');
        setTimeout(() => {
          window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
        }, 1000);
        return;
      }
      
      hasProcessed.current = true;
      setIsProcessing(true);
      
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const error = urlParams.get('error');

        if (error) {
          setStatus('error');
          setMessage(`Authorization failed: ${error}`);
          setTimeout(() => {
            window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
          }, 3000);
          return;
        }

        if (!code) {
          setStatus('error');
          setMessage('No authorization code received');
          setTimeout(() => {
            window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
          }, 3000);
          return;
        }

        // Check if this code has already been used or if data already exists
        const usedCodes = JSON.parse(sessionStorage.getItem('usedAuthCodes') || '[]');
        const existingParsedData = sessionStorage.getItem('parsedGoogleDocData');
        
        if (usedCodes.includes(code) || existingParsedData) {
          setStatus('success');
          setMessage('Authorization already processed. Redirecting...');
          setTimeout(() => {
            window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
          }, 2000);
          return;
        }

        // Get the pending Google Doc URL from session storage
        const pendingGoogleDocUrl = sessionStorage.getItem('pendingGoogleDocUrl');
        
        if (!pendingGoogleDocUrl) {
          setStatus('error');
          setMessage('No pending Google Doc URL found');
          setTimeout(() => {
            window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
          }, 3000);
          return;
        }

        setMessage('Fetching and parsing Google Doc...');

        // Exchange code and parse content
        let response;
        try {
          response = await apiClient.exchangeCodeAndParseContent(code, pendingGoogleDocUrl);
          // Only mark code as used after successful API call
          usedCodes.push(code);
          sessionStorage.setItem('usedAuthCodes', JSON.stringify(usedCodes));
        } catch (error: any) {
          if (error.response?.data?.detail?.includes('invalid_grant') || 
              error.response?.data?.detail?.includes('Authorization code is invalid')) {
            throw new Error('The authorization code has expired or been used already. Please try again by entering the Google Doc URL again.');
          }
          throw error;
        }
        
        // Check if response has the expected structure
        if (!response || !response.data) {
          throw new Error('Invalid response from server');
        }
        
        // Handle different response structures - parsed_data may be in various locations
        let parsedData;
        const responseData = response.data;
        
        // Check parsed_data in various locations (similar to auth_url extraction)
        if (responseData?.parsed_data) {
          parsedData = responseData.parsed_data;
        } else if (responseData?.metadata?.parsed_data) {
          parsedData = responseData.metadata.parsed_data;
        } else if (responseData?.agent_result?.parsed_data) {
          parsedData = responseData.agent_result.parsed_data;
        } else if ((response as any).parsed_data) {
          parsedData = (response as any).parsed_data;
        } else {
          // Last resort: try to find parsed_data anywhere in the response
          const findParsedData = (obj: any): any => {
            if (!obj || typeof obj !== 'object') return null;
            if (obj.parsed_data) return obj.parsed_data;
            for (const key in obj) {
              const result = findParsedData(obj[key]);
              if (result) return result;
            }
            return null;
          };
          const foundData = findParsedData(response);
          if (foundData) {
            parsedData = foundData;
          } else {
            console.error('Unexpected response structure. Full response:', response);
            throw new Error('Unexpected response structure from server. Expected parsed_data but got: ' + JSON.stringify(response).substring(0, 500));
          }
        }
        
        // Store the parsed data in session storage
        sessionStorage.setItem('parsedGoogleDocData', JSON.stringify(parsedData));
        sessionStorage.removeItem('pendingGoogleDocUrl');
        
        setStatus('success');
        setMessage('Google Doc parsed successfully! Redirecting...');
        
        // Redirect back to the GenSpec page
        setTimeout(() => {
          window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
        }, 2000);

      } catch (error) {
        console.error('Error processing Google Doc:', error);
        
        // Check if this is just a duplicate code error and data already exists
        const existingParsedData = sessionStorage.getItem('parsedGoogleDocData');
        if (existingParsedData && error instanceof Error && 
            (error.message.includes('invalid_grant') || error.message.includes('already been used'))) {
          setStatus('success');
          setMessage('Google Doc already processed. Redirecting...');
          setTimeout(() => {
            window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
          }, 2000);
          return;
        }
        
        setStatus('error');
        setMessage(`Error processing Google Doc: ${error instanceof Error ? error.message : 'Unknown error'}`);
        setTimeout(() => {
          window.location.href = '/agents-catalogue/micro-frontend/genspec-agent';
        }, 5000);
      }
    };

    processAuth();
  }, []); // Empty deps - only run once on mount

  const getStatusColor = () => {
    switch (status) {
      case 'processing': return '#007bff';
      case 'success': return '#28a745';
      case 'error': return '#dc3545';
      default: return '#007bff';
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh',
      fontFamily: 'Arial, sans-serif',
      backgroundColor: '#f8f9fa'
    }}>
      <div style={{ 
        textAlign: 'center',
        padding: '2rem',
        backgroundColor: 'white',
        borderRadius: '8px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
        maxWidth: '400px'
      }}>
        <div style={{
          width: '50px',
          height: '50px',
          borderRadius: '50%',
          backgroundColor: getStatusColor(),
          margin: '0 auto 1rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'white',
          fontSize: '24px'
        }}>
          {status === 'processing' && '⏳'}
          {status === 'success' && '✅'}
          {status === 'error' && '❌'}
        </div>
        <h2 style={{ margin: '0 0 1rem', color: '#333' }}>{message}</h2>
        {status === 'processing' && (
          <div style={{ 
            width: '100%', 
            height: '4px', 
            backgroundColor: '#e9ecef', 
            borderRadius: '2px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: '100%',
              height: '100%',
              backgroundColor: getStatusColor(),
              animation: 'pulse 1.5s ease-in-out infinite'
            }} />
          </div>
        )}
      </div>
      
      <style>{`
        @keyframes pulse {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
};

export default GoogleAuthCallback;
