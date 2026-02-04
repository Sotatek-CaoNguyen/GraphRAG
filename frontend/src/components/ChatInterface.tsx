'use client'

import { useState, useRef, useEffect, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ComparisonMetrics {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  analysis_time: number
  retrieval_time: number
  llm_time: number
  tokens_per_second: number
}

interface ComparisonResult {
  answer: string
  results_count: number
  metrics: ComparisonMetrics
}

interface ComparisonResponse {
  baseline: ComparisonResult
  graphrag: ComparisonResult
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  comparison?: ComparisonResponse
}

type ChatMode = 'graphrag' | 'baseline' | 'compare'

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [mode, setMode] = useState<ChatMode>('graphrag')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const submitQuestion = async (question: string) => {
    if (!question.trim() || isLoading) return

    const userMessage: Message = {
      role: 'user',
      content: question.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      // Use Next.js API route as proxy
      const endpoint = mode === 'compare'
        ? '/api/compare'
        : mode === 'baseline'
        ? '/api/baseline'
        : '/api/chat'
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: userMessage.content }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      const assistantMessage: Message = {
        role: 'assistant',
        content: mode === 'compare' ? '' : (data.answer || 'Sorry, I could not generate a response.'),
        timestamp: new Date()
      }

      if (mode === 'compare' && data?.baseline && data?.graphrag) {
        assistantMessage.comparison = data
      } else if (mode === 'compare') {
        assistantMessage.content = data.answer || 'Sorry, I could not generate a response.'
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error fetching response:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    await submitQuestion(input)
  }

  const handleSampleQuestionClick = (question: string) => {
    setInput(question)
    // Use setTimeout to ensure state is updated before submitting
    setTimeout(() => {
      submitQuestion(question)
    }, 0)
  }

  const renderCompareMeta = (metrics: ComparisonMetrics, resultsCount: number) => (
    <div className="compare-meta">
      <span>{resultsCount} results</span>
      <span>{metrics.retrieval_time.toFixed(2)}s retrieval</span>
      <span>{metrics.llm_time.toFixed(2)}s llm</span>
      <span>{metrics.total_tokens} tokens</span>
    </div>
  )

  return (
    <div className="cinema-shell">
      <header className="hero">
        <div className="hero-top">
          <div className="brand-mark">
            <span className="brand-eye" />
            <span className="brand-name">CineGraph Atlas</span>
          </div>
          <div className="status-pill">
            <span className="status-dot" />
            GraphRAG live
          </div>
        </div>
        <div className="hero-title">
          <h1>Every film, every link, one living graph.</h1>
          <p>Query actors, directors, genres, and story DNA with cinematic precision.</p>
        </div>
        <div className="hero-badges">
          <span>Neo4j</span>
          <span>GraphRAG</span>
          <span>OpenRouter</span>
        </div>
      </header>

      <main className="content-grid">
        <aside className="insight-panel">
          <div className="panel-card">
            <h2>Prompt vault</h2>
            <p>Tap a cue to fire a query or edit it to your taste.</p>
            <div className="sample-questions">
              <button
                type="button"
                onClick={() => handleSampleQuestionClick('"Which Crime movies are Joe Pesci in?"')}
                disabled={isLoading}
                className="sample-question-button"
              >
                Which Crime movies are Joe Pesci in?
              </button>
              <button
                type="button"
                onClick={() => handleSampleQuestionClick('"Which films directed by Christopher Nolan was Christian Bale in?"')}
                disabled={isLoading}
                className="sample-question-button"
              >
                Which films directed by Christopher Nolan was Christian Bale in?
              </button>
              <button
                type="button"
                onClick={() => handleSampleQuestionClick('"What movies are about Frodo?"')}
                disabled={isLoading}
                className="sample-question-button"
              >
                What movies are about Frodo?
              </button>
            </div>
          </div>
          <div className="panel-card mini">
            <h3>Studio notes</h3>
            <ul>
              <li>Find titles by cast, genre, or director pairs.</li>
              <li>Explore descriptions and ratings from the graph.</li>
              <li>Ask follow-ups to refine the result set.</li>
            </ul>
          </div>
        </aside>

        <section className="chat-panel">
          <div className="chat-head">
            <div>
              <h2>Ask the archive</h2>
              <p>Graph queries return structured grounding plus narrative insight.</p>
            </div>
            <div className="chat-actions">
              <div className="mode-toggle">
                <button
                  type="button"
                  className={mode === 'graphrag' ? 'active' : ''}
                  onClick={() => setMode('graphrag')}
                >
                  GraphRAG
                </button>
                <button
                  type="button"
                  className={mode === 'baseline' ? 'active' : ''}
                  onClick={() => setMode('baseline')}
                >
                  Baseline
                </button>
                <button
                  type="button"
                  className={mode === 'compare' ? 'active' : ''}
                  onClick={() => setMode('compare')}
                >
                  Compare
                </button>
              </div>
              <div className="chat-chip">
                {mode === 'compare' ? 'Comparison mode' : mode === 'baseline' ? 'Baseline mode' : 'GraphRAG mode'}
              </div>
            </div>
          </div>

          <div className="messages-container">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-card">
                  <p className="empty-title">Start with a movie hunch.</p>
                  <p className="empty-text">
                    {mode === 'compare'
                      ? 'Comparison mode runs baseline retrieval alongside GraphRAG.'
                      : mode === 'baseline'
                      ? 'Baseline mode uses keyword retrieval without graph expansion.'
                      : 'CineGraph turns every query into a connected map of films and people.'}
                  </p>
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={index}
                className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'}${
                  message.comparison ? ' message-compare' : ''
                }`}
                style={{ animationDelay: `${Math.min(index * 0.04, 0.6)}s` }}
              >
                {message.role === 'assistant' && message.comparison ? (
                  <>
                    <div className="compare-grid">
                      <div className="compare-card">
                        <div className="compare-head">
                          <h3>Baseline RAG</h3>
                          <span className="compare-pill">Keyword</span>
                        </div>
                        {renderCompareMeta(
                          message.comparison.baseline.metrics,
                          message.comparison.baseline.results_count
                        )}
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.comparison.baseline.answer}
                        </ReactMarkdown>
                      </div>
                      <div className="compare-card">
                        <div className="compare-head">
                          <h3>GraphRAG</h3>
                          <span className="compare-pill accent">Graph</span>
                        </div>
                        {renderCompareMeta(
                          message.comparison.graphrag.metrics,
                          message.comparison.graphrag.results_count
                        )}
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {message.comparison.graphrag.answer}
                        </ReactMarkdown>
                      </div>
                    </div>
                    <div className="message-timestamp">
                      {message.timestamp.toLocaleTimeString()}
                    </div>
                  </>
                ) : (
                  <>
                    <div className="message-content">
                      {message.role === 'assistant' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                      ) : (
                        message.content.split('\n').map((line, i) => (
                          <p key={i}>{line}</p>
                        ))
                      )}
                    </div>
                    <div className="message-timestamp">
                      {message.timestamp.toLocaleTimeString()}
                    </div>
                  </>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="message message-assistant">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="input-form">
            <div className="input-shell">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question about movies..."
                disabled={isLoading}
                className="chat-input"
              />
              <div className="input-hint">Enter to send</div>
            </div>
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="send-button"
            >
              {isLoading ? 'Thinking' : 'Send'}
            </button>
          </form>
        </section>
      </main>

      <style jsx>{`
        .cinema-shell {
          min-height: 100vh;
          padding: 2.5rem clamp(1.5rem, 4vw, 3.5rem) 3rem;
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }

        .hero {
          background: linear-gradient(120deg, rgba(255, 255, 255, 0.8), rgba(250, 244, 230, 0.85));
          border: 1px solid var(--border);
          border-radius: 24px;
          padding: clamp(1.75rem, 3vw, 2.5rem);
          box-shadow: var(--shadow);
          position: relative;
          overflow: hidden;
          animation: rise 0.8s ease;
        }

        .hero::after {
          content: '';
          position: absolute;
          inset: 0;
          background: radial-gradient(circle at 10% 20%, rgba(231, 111, 81, 0.15), transparent 45%),
            radial-gradient(circle at 90% 0%, rgba(42, 157, 143, 0.12), transparent 50%),
            repeating-linear-gradient(90deg, rgba(0, 0, 0, 0.04) 0 6px, transparent 6px 12px);
          opacity: 0.7;
          pointer-events: none;
        }

        .hero-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          position: relative;
          z-index: 1;
        }

        .brand-mark {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          font-family: var(--font-display);
          text-transform: uppercase;
          letter-spacing: 0.08em;
          font-size: 1.2rem;
          color: var(--ink);
        }

        .brand-eye {
          width: 48px;
          height: 32px;
          border-radius: 999px;
          background: linear-gradient(120deg, var(--accent), var(--gold));
          position: relative;
          box-shadow: 0 10px 24px rgba(231, 111, 81, 0.35);
          animation: pulse 3s ease-in-out infinite;
        }

        .brand-eye::after {
          content: '';
          position: absolute;
          inset: 8px 16px;
          border-radius: 999px;
          background: var(--ink);
        }

        .status-pill {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.35rem 0.8rem;
          border-radius: 999px;
          background: rgba(42, 157, 143, 0.12);
          color: var(--ink);
          font-weight: 600;
          font-size: 0.85rem;
        }

        .status-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--accent-2);
          box-shadow: 0 0 0 4px rgba(42, 157, 143, 0.2);
        }

        .hero-title {
          margin-top: 1.5rem;
          max-width: 720px;
          position: relative;
          z-index: 1;
        }

        .hero-title h1 {
          font-family: var(--font-display);
          font-size: clamp(2.2rem, 4vw, 3.4rem);
          letter-spacing: 0.05em;
          text-transform: uppercase;
          margin-bottom: 0.5rem;
          color: var(--ink);
        }

        .hero-title p {
          font-size: 1.05rem;
          color: var(--ink-soft);
        }

        .hero-badges {
          margin-top: 1.5rem;
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          position: relative;
          z-index: 1;
        }

        .hero-badges span {
          padding: 0.35rem 0.8rem;
          border-radius: 999px;
          border: 1px solid rgba(0, 0, 0, 0.1);
          background: rgba(255, 255, 255, 0.7);
          font-size: 0.85rem;
          font-weight: 600;
          letter-spacing: 0.02em;
        }

        .content-grid {
          display: grid;
          grid-template-columns: minmax(0, 320px) minmax(0, 1fr);
          gap: 1.5rem;
        }

        .insight-panel {
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }

        .panel-card {
          padding: 1.5rem;
          border-radius: 20px;
          background: rgba(255, 255, 255, 0.85);
          border: 1px solid var(--border);
          box-shadow: var(--shadow);
          animation: float-in 0.8s ease;
        }

        .panel-card h2,
        .panel-card h3 {
          font-family: var(--font-display);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.5rem;
          font-size: 1.5rem;
        }

        .panel-card p {
          color: var(--ink-soft);
          margin-bottom: 1rem;
        }

        .panel-card.mini ul {
          list-style: none;
          display: grid;
          gap: 0.75rem;
          color: var(--ink-soft);
          font-size: 0.95rem;
        }

        .panel-card.mini li {
          padding-left: 1.25rem;
          position: relative;
        }

        .panel-card.mini li::before {
          content: '';
          position: absolute;
          left: 0;
          top: 0.35rem;
          width: 0.55rem;
          height: 0.55rem;
          border-radius: 50%;
          background: var(--accent);
          box-shadow: 0 0 0 4px rgba(231, 111, 81, 0.2);
        }

        .sample-questions {
          display: grid;
          gap: 0.75rem;
        }

        .sample-question-button {
          width: 100%;
          text-align: left;
          padding: 0.9rem 1rem;
          border-radius: 14px;
          border: 1px solid rgba(0, 0, 0, 0.08);
          background: linear-gradient(120deg, rgba(255, 255, 255, 0.9), rgba(255, 244, 224, 0.7));
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--ink);
          cursor: pointer;
          transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        }

        .sample-question-button:hover:not(:disabled) {
          transform: translateY(-2px);
          border-color: rgba(231, 111, 81, 0.4);
          box-shadow: 0 10px 20px rgba(231, 111, 81, 0.2);
        }

        .sample-question-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .chat-panel {
          display: flex;
          flex-direction: column;
          background: rgba(255, 255, 255, 0.82);
          border-radius: 24px;
          border: 1px solid var(--border);
          box-shadow: var(--shadow);
          overflow: hidden;
          min-height: 600px;
        }

        .chat-head {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 1rem;
          padding: 1.5rem 1.75rem 1rem;
          border-bottom: 1px solid rgba(0, 0, 0, 0.08);
          background: linear-gradient(120deg, rgba(255, 255, 255, 0.9), rgba(233, 196, 106, 0.15));
        }

        .chat-head h2 {
          font-family: var(--font-display);
          text-transform: uppercase;
          letter-spacing: 0.06em;
          font-size: 1.6rem;
          margin-bottom: 0.35rem;
        }

        .chat-head p {
          color: var(--ink-soft);
          max-width: 520px;
        }

        .chat-actions {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 0.6rem;
        }

        .mode-toggle {
          display: inline-flex;
          padding: 0.2rem;
          border-radius: 999px;
          background: rgba(0, 0, 0, 0.06);
          border: 1px solid rgba(0, 0, 0, 0.08);
        }

        .mode-toggle button {
          border: none;
          background: transparent;
          padding: 0.35rem 0.85rem;
          border-radius: 999px;
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          font-weight: 600;
          color: var(--ink-soft);
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .mode-toggle button.active {
          background: #fff;
          color: var(--ink);
          box-shadow: 0 6px 14px rgba(0, 0, 0, 0.08);
        }

        .chat-chip {
          padding: 0.4rem 0.8rem;
          border-radius: 999px;
          background: rgba(231, 111, 81, 0.12);
          color: var(--ink);
          font-weight: 600;
          font-size: 0.85rem;
        }

        .messages-container {
          flex: 1;
          overflow-y: auto;
          padding: 1.5rem 1.75rem;
          background: linear-gradient(180deg, rgba(255, 255, 255, 0.6), rgba(247, 241, 230, 0.85));
          position: relative;
        }

        .messages-container::after {
          content: '';
          position: absolute;
          inset: 0;
          background-image: repeating-linear-gradient(
            0deg,
            rgba(0, 0, 0, 0.03) 0px,
            rgba(0, 0, 0, 0.03) 1px,
            transparent 1px,
            transparent 18px
          );
          pointer-events: none;
          opacity: 0.4;
        }

        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 240px;
          position: relative;
          z-index: 1;
        }

        .empty-card {
          padding: 2rem;
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.9);
          border: 1px dashed rgba(0, 0, 0, 0.15);
          text-align: center;
          max-width: 420px;
        }

        .empty-title {
          font-family: var(--font-display);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          font-size: 1.4rem;
          margin-bottom: 0.5rem;
        }

        .empty-text {
          color: var(--ink-soft);
        }

        .message {
          display: flex;
          flex-direction: column;
          gap: 0.35rem;
          margin-bottom: 1.25rem;
          animation: message-in 0.4s ease forwards;
          opacity: 0;
          position: relative;
          z-index: 1;
        }

        .message-user {
          align-items: flex-end;
        }

        .message-assistant {
          align-items: flex-start;
        }

        .message-compare {
          align-items: stretch;
        }

        .compare-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 1rem;
        }

        .compare-card {
          background: rgba(255, 255, 255, 0.95);
          border: 1px solid rgba(0, 0, 0, 0.08);
          border-radius: 18px;
          padding: 1rem 1.1rem;
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
        }

        .compare-head {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 0.75rem;
          margin-bottom: 0.5rem;
        }

        .compare-head h3 {
          font-family: var(--font-display);
          text-transform: uppercase;
          letter-spacing: 0.06em;
          font-size: 1.1rem;
        }

        .compare-pill {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          padding: 0.25rem 0.6rem;
          border-radius: 999px;
          background: rgba(0, 0, 0, 0.06);
          color: var(--ink-soft);
        }

        .compare-pill.accent {
          background: rgba(42, 157, 143, 0.18);
          color: var(--ink);
        }

        .compare-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 0.4rem;
          margin-bottom: 0.8rem;
          font-size: 0.72rem;
          color: var(--ink-soft);
        }

        .compare-meta span {
          background: rgba(0, 0, 0, 0.05);
          padding: 0.2rem 0.5rem;
          border-radius: 999px;
        }

        .message-content {
          max-width: min(70%, 540px);
          padding: 1rem 1.2rem;
          border-radius: 18px;
          background: rgba(255, 255, 255, 0.95);
          border: 1px solid rgba(0, 0, 0, 0.08);
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
          line-height: 1.5;
        }

        .message-user .message-content {
          background: linear-gradient(135deg, rgba(231, 111, 81, 0.9), rgba(244, 162, 97, 0.95));
          color: #1a1a1a;
          border: none;
        }

        .message-assistant .message-content {
          border-left: 4px solid var(--accent-2);
        }

        .message-timestamp {
          font-size: 0.75rem;
          color: rgba(0, 0, 0, 0.5);
        }

        .typing-indicator {
          display: inline-flex;
          gap: 0.5rem;
          align-items: center;
        }

        .typing-indicator span {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--accent-2);
          animation: typing 1.4s infinite;
        }

        .typing-indicator span:nth-child(2) {
          animation-delay: 0.2s;
        }

        .typing-indicator span:nth-child(3) {
          animation-delay: 0.4s;
        }

        .input-form {
          display: flex;
          gap: 1rem;
          padding: 1.25rem 1.5rem 1.5rem;
          border-top: 1px solid rgba(0, 0, 0, 0.08);
          background: rgba(255, 255, 255, 0.9);
        }

        .input-shell {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .chat-input {
          width: 100%;
          padding: 0.9rem 1.1rem;
          border-radius: 16px;
          border: 1px solid rgba(0, 0, 0, 0.12);
          background: rgba(255, 255, 255, 0.9);
          font-size: 1rem;
          outline: none;
          transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .chat-input:focus {
          border-color: rgba(42, 157, 143, 0.6);
          box-shadow: 0 0 0 4px rgba(42, 157, 143, 0.15);
        }

        .chat-input:disabled {
          background: rgba(240, 240, 240, 0.9);
          cursor: not-allowed;
        }

        .input-hint {
          font-size: 0.8rem;
          color: rgba(0, 0, 0, 0.5);
          padding-left: 0.5rem;
        }

        .send-button {
          align-self: flex-start;
          padding: 0.9rem 2.2rem;
          border-radius: 999px;
          border: none;
          font-weight: 700;
          letter-spacing: 0.03em;
          text-transform: uppercase;
          background: linear-gradient(135deg, var(--accent), var(--gold));
          color: var(--ink);
          cursor: pointer;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
          box-shadow: 0 12px 24px rgba(231, 111, 81, 0.25);
        }

        .send-button:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 16px 30px rgba(231, 111, 81, 0.3);
        }

        .send-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
          box-shadow: none;
        }

        /* Markdown styles for assistant messages */
        .message-assistant .message-content :global(h1),
        .message-assistant .message-content :global(h2),
        .message-assistant .message-content :global(h3),
        .message-assistant .message-content :global(h4),
        .message-assistant .message-content :global(h5),
        .message-assistant .message-content :global(h6),
        .compare-card :global(h1),
        .compare-card :global(h2),
        .compare-card :global(h3),
        .compare-card :global(h4),
        .compare-card :global(h5),
        .compare-card :global(h6) {
          margin: 0.75rem 0 0.5rem 0;
          font-weight: 700;
          line-height: 1.3;
        }

        .message-assistant .message-content :global(h1),
        .compare-card :global(h1) {
          font-size: 1.4rem;
        }

        .message-assistant .message-content :global(h2),
        .compare-card :global(h2) {
          font-size: 1.25rem;
        }

        .message-assistant .message-content :global(h3),
        .compare-card :global(h3) {
          font-size: 1.1rem;
        }

        .message-assistant .message-content :global(ul),
        .message-assistant .message-content :global(ol),
        .compare-card :global(ul),
        .compare-card :global(ol) {
          margin: 0.5rem 0;
          padding-left: 1.5rem;
        }

        .message-assistant .message-content :global(li),
        .compare-card :global(li) {
          margin: 0.3rem 0;
        }

        .message-assistant .message-content :global(code),
        .compare-card :global(code) {
          background: rgba(0, 0, 0, 0.06);
          padding: 0.2rem 0.4rem;
          border-radius: 3px;
          font-family: 'Courier New', monospace;
          font-size: 0.9em;
        }

        .message-assistant .message-content :global(pre),
        .compare-card :global(pre) {
          background: rgba(0, 0, 0, 0.06);
          padding: 0.75rem;
          border-radius: 6px;
          overflow-x: auto;
          margin: 0.6rem 0;
        }

        .message-assistant .message-content :global(pre code),
        .compare-card :global(pre code) {
          background: none;
          padding: 0;
        }

        .message-assistant .message-content :global(blockquote),
        .compare-card :global(blockquote) {
          border-left: 3px solid var(--accent);
          padding-left: 1rem;
          margin: 0.5rem 0;
          color: var(--ink-soft);
          font-style: italic;
        }

        .message-assistant .message-content :global(a),
        .compare-card :global(a) {
          color: var(--accent-2);
          text-decoration: underline;
        }

        .message-assistant .message-content :global(hr),
        .compare-card :global(hr) {
          border: none;
          border-top: 1px solid rgba(0, 0, 0, 0.1);
          margin: 1rem 0;
        }

        .message-assistant .message-content :global(table),
        .compare-card :global(table) {
          border-collapse: collapse;
          width: 100%;
          margin: 1rem 0;
          font-size: 0.92em;
        }

        .message-assistant .message-content :global(th),
        .message-assistant .message-content :global(td),
        .compare-card :global(th),
        .compare-card :global(td) {
          border: 1px solid rgba(0, 0, 0, 0.12);
          padding: 0.6rem;
          text-align: left;
        }

        .message-assistant .message-content :global(th),
        .compare-card :global(th) {
          background: rgba(0, 0, 0, 0.04);
          font-weight: 600;
        }

        .message-assistant .message-content :global(tr:nth-child(even)),
        .compare-card :global(tr:nth-child(even)) {
          background: rgba(0, 0, 0, 0.02);
        }

        @keyframes typing {
          0%, 60%, 100% {
            transform: translateY(0);
            opacity: 0.6;
          }
          30% {
            transform: translateY(-8px);
            opacity: 1;
          }
        }

        @keyframes rise {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes float-in {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes message-in {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes pulse {
          0%, 100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.04);
          }
        }

        @media (max-width: 960px) {
          .content-grid {
            grid-template-columns: 1fr;
          }

          .chat-panel {
            min-height: 520px;
          }

          .input-form {
            flex-direction: column;
            align-items: stretch;
          }

          .send-button {
            width: 100%;
          }
        }

        @media (max-width: 640px) {
          .cinema-shell {
            padding: 1.75rem 1.25rem 2.5rem;
          }

          .chat-head {
            flex-direction: column;
            align-items: flex-start;
          }

          .chat-actions {
            align-items: flex-start;
          }

          .hero-top {
            flex-direction: column;
            align-items: flex-start;
          }

          .message-content {
            max-width: 100%;
          }
        }
      `}</style>
    </div>
  )
}
