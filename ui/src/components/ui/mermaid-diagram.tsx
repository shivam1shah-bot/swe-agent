/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import React, { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    mermaid: any;
  }
}

interface MermaidDiagramProps {
  content: string;
  className?: string;
  isLoading?: boolean;
  error?: string | null;
}

export const MermaidDiagram: React.FC<MermaidDiagramProps> = ({
  content,
  className = '',
  isLoading = false,
  error
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  // Load Mermaid from CDN
  useEffect(() => {
    if (window.mermaid) {
      setIsInitialized(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/mermaid@10.9.0/dist/mermaid.min.js';
    script.onload = () => {
      if (window.mermaid) {
        window.mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose'
        });
        setIsInitialized(true);
      }
    };
    script.onerror = () => setRenderError('Failed to load Mermaid library');
    document.head.appendChild(script);
  }, []);

  // Render diagram when ready
  useEffect(() => {
    if (!isInitialized || !content || !containerRef.current || isLoading || error) {
      return;
    }

    const renderDiagram = async () => {
      try {
        setRenderError(null);
        
        // Clean the content - remove config blocks
        let cleanContent = content;
        if (content.includes('---\nconfig:')) {
          const configEnd = content.indexOf('---\ngraph');
          if (configEnd > -1) {
            cleanContent = content.substring(configEnd + 4);
          }
        }

        // Remove class definitions for compatibility
        const lines = cleanContent.split('\n');
        const graphLines = lines.filter(line => {
          const trimmed = line.trim();
          return trimmed && 
                 !trimmed.startsWith('classDef') && 
                 !trimmed.includes(':::');
        });
        cleanContent = graphLines.join('\n');

        // Render
        const diagramId = `mermaid-${Date.now()}`;
        const svg = await window.mermaid.render(diagramId, cleanContent);
        
        if (containerRef.current) {
          // nosemgrep: typescript.react.security.audit.react-unsanitized-property.react-unsanitized-property
          containerRef.current.innerHTML = svg.svg || svg;
        }
      } catch (_err) {
        setRenderError('Unable to render diagram');
      }
    };

    renderDiagram();
  }, [content, isInitialized, isLoading, error]);

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
        <div className="text-gray-600">Loading diagram...</div>
      </div>
    );
  }

  if (error || renderError) {
    return (
      <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
        <div className="text-gray-600">Graph not available</div>
      </div>
    );
  }

  if (!content) {
    return (
      <div className={`flex items-center justify-center min-h-[200px] ${className}`}>
        <div className="text-gray-600">No diagram data</div>
      </div>
    );
  }

  return (
    <div 
      ref={containerRef}
      className={`w-full ${className}`}
      style={{ minHeight: '200px' }}
    />
  );
};

export default MermaidDiagram;