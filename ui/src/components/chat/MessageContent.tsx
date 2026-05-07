/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MessageContentProps {
  content: string;
  role: 'user' | 'assistant';
  className?: string;
}

export function MessageContent({ content, className }: MessageContentProps) {
  return (
    <div className={cn("prose prose-sm max-w-none", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Custom code block rendering
          code({ className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const isInline = !className || !match;
            
            return !isInline ? (
              <pre className="bg-gray-100 border border-gray-200 rounded-md p-3 overflow-x-auto my-2">
                <code className="text-sm font-mono text-gray-800">
                  {String(children).replace(/\n$/, '')}
                </code>
              </pre>
            ) : (
              <code 
                className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm font-mono" 
                {...props}
              >
                {children}
              </code>
            );
          },
          // Custom list styling
          ul({ children }: any) {
            return <ul className="list-disc list-inside space-y-1 my-2">{children}</ul>;
          },
          ol({ children }: any) {
            return <ol className="list-decimal list-inside space-y-1 my-2">{children}</ol>;
          },
          // Custom paragraph styling
          p({ children }: any) {
            return <p className="mb-2 last:mb-0">{children}</p>;
          },
          // Custom table styling
          table({ children }: any) {
            return (
              <div className="overflow-x-auto my-4">
                <table className="min-w-full border border-gray-200 rounded-md">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }: any) {
            return (
              <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left text-sm font-medium text-gray-900">
                {children}
              </th>
            );
          },
          td({ children }: any) {
            return (
              <td className="border border-gray-200 px-3 py-2 text-sm text-gray-700">
                {children}
              </td>
            );
          },
          // Custom blockquote styling
          blockquote({ children }: any) {
            return (
              <blockquote className="border-l-4 border-blue-200 pl-4 italic text-gray-600 my-2">
                {children}
              </blockquote>
            );
          },
          // Custom heading styling
          h1({ children }: any) {
            return <h1 className="text-xl font-bold mb-2 mt-4 first:mt-0">{children}</h1>;
          },
          h2({ children }: any) {
            return <h2 className="text-lg font-semibold mb-2 mt-3 first:mt-0">{children}</h2>;
          },
          h3({ children }: any) {
            return <h3 className="text-base font-semibold mb-1 mt-2 first:mt-0">{children}</h3>;
          },
          // Custom link styling
          a({ children, href }: any) {
            return (
              <a 
                href={href} 
                className="text-blue-600 hover:text-blue-800 underline" 
                target="_blank" 
                rel="noopener noreferrer"
              >
                {children}
              </a>
            );
          },
          // Custom horizontal rule
          hr() {
            return <hr className="border-gray-200 my-4" />;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
