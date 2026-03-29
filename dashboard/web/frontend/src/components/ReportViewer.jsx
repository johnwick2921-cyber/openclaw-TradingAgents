import { useState } from 'react';
import Markdown from 'react-markdown';

export default function ReportViewer({ title, content, defaultExpanded = true }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  if (!content) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = content;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{
        backgroundColor: 'var(--bg-secondary)',
        borderColor: 'var(--border)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
        style={{ borderBottom: expanded ? '1px solid var(--border)' : 'none' }}
        onClick={() => setExpanded((prev) => !prev)}
      >
        <div className="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`h-4 w-4 transition-transform ${expanded ? 'rotate-90' : ''}`}
            style={{ color: 'var(--text-secondary)' }}
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
              clipRule="evenodd"
            />
          </svg>
          <h3
            className="text-sm font-semibold"
            style={{ color: 'var(--text-primary)' }}
          >
            {title}
          </h3>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            handleCopy();
          }}
          className="text-xs px-2 py-1 rounded-md transition-colors hover:opacity-80"
          style={{
            color: copied ? 'var(--success)' : 'var(--text-secondary)',
            backgroundColor: 'var(--bg-tertiary)',
          }}
          title="Copy to clipboard"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      {/* Content */}
      {expanded && (
        <div
          className="px-4 py-3 prose prose-sm max-w-none overflow-x-auto"
          style={{ color: 'var(--text-primary)' }}
        >
          <Markdown
            components={{
              h1: ({ children }) => (
                <h1 className="text-lg font-bold mt-4 mb-2" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-base font-bold mt-3 mb-2" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-sm font-bold mt-2 mb-1" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </h3>
              ),
              p: ({ children }) => (
                <p className="text-sm mb-2 leading-relaxed" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </p>
              ),
              ul: ({ children }) => (
                <ul className="text-sm list-disc pl-5 mb-2 space-y-1" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="text-sm list-decimal pl-5 mb-2 space-y-1" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </ol>
              ),
              code: ({ children, className }) => {
                const isBlock = className?.includes('language-');
                if (isBlock) {
                  return (
                    <pre
                      className="text-xs rounded-lg p-3 my-2 overflow-x-auto"
                      style={{ backgroundColor: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}
                    >
                      <code>{children}</code>
                    </pre>
                  );
                }
                return (
                  <code
                    className="text-xs px-1 py-0.5 rounded"
                    style={{ backgroundColor: 'var(--bg-tertiary)' }}
                  >
                    {children}
                  </code>
                );
              },
              pre: ({ children }) => <>{children}</>,
              strong: ({ children }) => (
                <strong className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {children}
                </strong>
              ),
              blockquote: ({ children }) => (
                <blockquote
                  className="border-l-4 pl-3 my-2 text-sm italic"
                  style={{ borderColor: 'var(--accent)', color: 'var(--text-secondary)' }}
                >
                  {children}
                </blockquote>
              ),
            }}
          >
            {content}
          </Markdown>
        </div>
      )}
    </div>
  );
}
