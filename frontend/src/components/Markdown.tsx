import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { memo } from "react";

// Lightweight markdown renderer with GitHub-flavoured extensions
// (tables, strikethrough) and syntax-highlighted code blocks.
function MarkdownBase({ content }: { content: string }) {
  return (
    <div className="markdown msg-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

export const Markdown = memo(MarkdownBase);
