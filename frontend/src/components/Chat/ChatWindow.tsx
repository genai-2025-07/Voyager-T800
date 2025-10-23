// src/components/Chat/ChatWindow.tsx
import React, { useEffect, useRef, useState } from "react";
import { X, Send, Image as ImageIcon, Loader2, StopCircle } from "lucide-react";
import { useAuth } from "../../contexts/AuthContext";
import { useSessions } from "../../contexts/SessionsContext";
import { useToast } from "../../ui/toast-provider";
import { apiClient } from "../../api/apiClient";
import { compressImage, MAX_IMAGE_SIZE } from "../../utils/image";
import type { Message } from "../../types";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import rehypeSanitize from "rehype-sanitize";

const PREVIEW_IMAGE_LARGEST_SIZE = 400;

const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState("");
  const [summarizationTriggered, setSummarizationTriggered] = useState(false);
  const [tokenLimitReached, setTokenLimitReached] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  // reader for fetch-based streaming
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(
    null
  );
  // keep the active session id for stop requests
  const activeSessionIdRef = useRef<string | undefined>(undefined);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isStreamingRef = useRef<boolean>(false);

  const { user, isGuest } = useAuth();
  const { currentSession, guestMessages, guestSessionId, addMessageToGuest, updateLastGuestMessage, createSession, openSession } =
    useSessions();
  const { showToast } = useToast();

  const startNewConversation = () => {
    setMessages([]);
    setTokenLimitReached(false);
    setSummarizationTriggered(false);
    setError("");
    setInput("");
    setImage(null);
    setImagePreview(null);
    
    // Create a new session
    if (isGuest) {
      // For guests, we don't need to create a new session on the backend
      // The session will be created automatically on the next request
      showToast(
        "New conversation started",
        "You can now continue chatting in a fresh session."
      );
    }
  };

  useEffect(() => {
    if (isGuest) {
      setMessages(guestMessages);
    } else if (currentSession?.messages) {
      // Only prevent updating if we're currently streaming (to avoid overwriting user input)
      // Otherwise, always update when switching sessions
      setMessages(prev => isStreamingRef.current ? prev : currentSession.messages);
    } else {
      setMessages([]);
    }
  }, [currentSession, guestMessages, isGuest]);

  // Sync ref with streaming state
  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  // Show toast notification when summarization is triggered
  useEffect(() => {
    if (summarizationTriggered && !isGuest) {
      showToast(
        'Conversation Summarized',
        'Your chat history has been summarized to save memory. Recent messages are preserved.'
      );
      setSummarizationTriggered(false);
    }
  }, [summarizationTriggered, isGuest, showToast]);

  // Debug: log messages whenever they change
  useEffect(() => {
    console.log("Chat messages state:", messages);
    // console.table(messages); // optional: nicer tabular view for arrays/objects
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");

    if (file.size > MAX_IMAGE_SIZE) {
      try {
        const compressed = await compressImage(file, MAX_IMAGE_SIZE);
        setImage(compressed);
        setImagePreview(URL.createObjectURL(compressed));
      } catch (err) {
        setError(
          "Image is too large and could not be compressed. Please choose a smaller image."
        );
      }
    } else {
      setImage(file);
      setImagePreview(URL.createObjectURL(file));
    }
  };

  const stopStreaming = async () => {
    try {
      // Close SSE if present
      if (eventSourceRef.current) {
        try {
          eventSourceRef.current.close();
        } catch (err) {
          console.warn("Error closing EventSource:", err);
        }
        eventSourceRef.current = null;
      }

      // Cancel fetch reader if present
      if (readerRef.current) {
        try {
          // reader.cancel() returns a Promise; await it to ensure stream is stopped
          await readerRef.current.cancel();
        } catch (err) {
          console.warn("Error cancelling stream reader:", err);
        }
        readerRef.current = null;
      }

      // Inform server to stop generation (only if we have a session id)
      const sessionIdToStop = activeSessionIdRef.current;
      if (sessionIdToStop) {
        try {
          await apiClient.stopGeneration(sessionIdToStop, user?.sub, isGuest);
        } catch (err) {
          console.warn("Failed to call stopGeneration on server:", err);
          // don't surface this as fatal to user — stopping local stream is primary
        }
      }
    } finally {
      setIsStreaming(false);
      activeSessionIdRef.current = undefined;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() && !image) return;
    if (isStreaming) return;

    setError("");
    setIsStreaming(true);

    const userMessage: Message = {
      sender: "user",
      content: input,
      image_url: imagePreview || undefined,
      timestamp: Date.now(),
    };

    const assistantMessage: Message = {
      sender: "assistant",
      content: "",
      timestamp: Date.now(),
    };

    if (isGuest) {
      // For guest: add both messages to context first
      addMessageToGuest(userMessage);
      addMessageToGuest(assistantMessage);
    } else {
      // For logged-in users: update local state directly
      setMessages((prev) => [...prev, userMessage, assistantMessage]);
    }

    // For guests, use guestSessionId from context; for authenticated users, use currentSession
    let sessionId = isGuest ? guestSessionId : currentSession?.session_id;

    try {
      // Create session if we don't have one (for both guests and authenticated users)
      if (!sessionId) {
        sessionId = await createSession();
        
        // For authenticated users, load the session to set currentSession
        if (!isGuest && user?.sub) {
          await openSession(sessionId);
        }
      }

      activeSessionIdRef.current = sessionId;

      const connection = apiClient.createStreamConnection(
        input,
        sessionId,
        user?.sub,
        image || undefined,
        isGuest
      );

      const response = await connection;
      const reader = response.body?.getReader();
      if (reader) readerRef.current = reader;
      const decoder = new TextDecoder();

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.done) {
                  setIsStreaming(false);
                  activeSessionIdRef.current = undefined;
                } 
                if (data.chunk) {
                  if (isGuest) {
                    // For guest: append chunks to the last message
                    updateLastGuestMessage((prevContent) => prevContent + data.chunk);
                  } else {
                    // For logged-in users: update local state
                    setMessages((prev) => {
                      const updated = [...prev];
                      const lastMsg = updated[updated.length - 1];
                      if (lastMsg.sender === "assistant") {
                        lastMsg.content += data.chunk;
                      }
                      return updated;
                    });
                  }
                }
                
                if (data.summarization_occurred === true) {
                  setSummarizationTriggered(true);
                }
                else if (data.page_refresh_required === true) {
                  setTokenLimitReached(true);
                  showToast(
                    "Token limit reached",
                    "Your conversation has reached the token limit. Please start a new conversation to continue."
                  );
                }
              } catch (err) {
                console.error("Error parsing stream data:", err);
              }
            }
          }
        }

        readerRef.current = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setIsStreaming(false);
      activeSessionIdRef.current = undefined;
      if (readerRef.current) {
        try {
          await readerRef.current.cancel();
        } catch (e) {
          console.warn("Error cancelling reader after failure:", e);
        }
        readerRef.current = null;
      }
    }

    setInput("");
    setImage(null);
    setImagePreview(null);
  };

  return (
    <div className="flex flex-col h-full bg-background">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-pastel">
        
        {messages.length === 0 ? (
          <div className="text-center text-muted-foreground mt-20">
            <h2 className="text-2xl font-bold mb-2 text-foreground">
              Welcome to Voyager-T800
            </h2>
            <p>I'm your intelligent AI travel assistant. Tell me about your dream trip - where would you like to go, when, and what kind of experience are you looking for?</p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex w-full ${
                msg.sender === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`flex flex-col ${
                  msg.sender === "user" ? "items-end" : "items-start"
                } max-w-[70%]`}
              >
                <div
                  className={`rounded-xl p-4 shadow-sm ${
                    msg.sender === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-card text-card-foreground border border-border"
                  }`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw, rehypeSanitize]}
                    components={{
                      // Links
                      a: ({ node, ...props }) => (
                        <a
                          className="text-blue-500 hover:underline font-medium"
                          target="_blank"
                          rel="noopener noreferrer"
                          {...props}
                        />
                      ),
                      // Paragraphs
                      p: ({ node, ...props }) => (
                        <p className="mb-2 last:mb-0" {...props} />
                      ),
                      // Headings
                      h1: ({ node, ...props }) => (
                        <h1
                          className="text-2xl font-bold mb-3 mt-4 first:mt-0"
                          {...props}
                        />
                      ),
                      h2: ({ node, ...props }) => (
                        <h2
                          className="text-xl font-bold mb-2 mt-3 first:mt-0"
                          {...props}
                        />
                      ),
                      h3: ({ node, ...props }) => (
                        <h3
                          className="text-lg font-semibold mb-2 mt-2 first:mt-0"
                          {...props}
                        />
                      ),
                      // Lists
                      ul: ({ node, ...props }) => (
                        <ul
                          className="list-disc list-inside mb-2 space-y-1"
                          {...props}
                        />
                      ),
                      ol: ({ node, ...props }) => (
                        <ol
                          className="list-decimal list-inside mb-2 space-y-1"
                          {...props}
                        />
                      ),
                      li: ({ node, ...props }) => (
                        <li className="ml-2" {...props} />
                      ),
                      // Code
                      code: ({ node, inline, ...props }: any) =>
                        inline ? (
                          <code
                            className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono"
                            {...props}
                          />
                        ) : (
                          <code
                            className="block bg-muted p-3 rounded-lg text-sm font-mono overflow-x-auto mb-2"
                            {...props}
                          />
                        ),
                      pre: ({ node, ...props }) => (
                        <pre
                          className="bg-muted p-3 rounded-lg overflow-x-auto mb-2"
                          {...props}
                        />
                      ),
                      // Blockquote
                      blockquote: ({ node, ...props }) => (
                        <blockquote
                          className="border-l-4 border-primary pl-4 italic my-2"
                          {...props}
                        />
                      ),
                      // Strong/Bold
                      strong: ({ node, ...props }) => (
                        <strong className="font-bold" {...props} />
                      ),
                      // Emphasis/Italic
                      em: ({ node, ...props }) => (
                        <em className="italic" {...props} />
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                  {msg.sender === "assistant" &&
                    !msg.content &&
                    isStreaming && (
                      <Loader2
                        className="animate-spin text-primary"
                        size={20}
                      />
                    )}
                </div>
                {msg.sender === "user" && msg.image_url && (
                  <img
                    src={msg.image_url}
                    alt="Uploaded itinerary image"
                    className="rounded-lg mt-2 border border-border self-end"
                    style={{
                      maxWidth: `${PREVIEW_IMAGE_LARGEST_SIZE}px`,
                      maxHeight: `${PREVIEW_IMAGE_LARGEST_SIZE}px`,
                      width: "auto",
                      height: "auto",
                      objectFit: "contain",
                    }}
                  />
                )}
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="mx-4 mb-2 bg-destructive/10 text-destructive-foreground p-3 rounded-lg text-sm border border-destructive/20">
          {error}
        </div>
      )}

      {tokenLimitReached && (
        <div className="mx-4 mb-2 bg-destructive/10 border border-destructive/20 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-destructive rounded-full"></div>
              <div>
                <h3 className="font-semibold text-destructive">Token Limit Reached</h3>
                <p className="text-sm text-muted-foreground">
                  Your conversation has reached the tokens limit. Start a new conversation or log in to continue chatting.
                </p>
              </div>
            </div>
            <button
              onClick={startNewConversation}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors text-sm font-medium"
            >
              Start New Conversation
            </button>
          </div>
        </div>
      )}

      <div className="border-t border-border p-4 bg-card">
        <form onSubmit={handleSubmit} className="flex flex-col gap-2">
          {imagePreview && (
            <div className="relative inline-block">
              <img
                src={imagePreview}
                alt="Preview"
                className="h-20 rounded-lg border border-border"
              />
              <button
                type="button"
                onClick={() => {
                  setImage(null);
                  setImagePreview(null);
                }}
                className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full p-1 hover:opacity-90 transition-opacity shadow-md"
              >
                <X size={14} />
              </button>
            </div>
          )}

          <div className="flex gap-2">
            <label className={`cursor-pointer hover:bg-muted p-2 rounded-lg flex items-center justify-center border border-border transition-colors ${tokenLimitReached ? 'opacity-50 cursor-not-allowed' : ''}`}>
              <ImageIcon size={24} className="text-muted-foreground" />
              <input
                type="file"
                accept="image/*"
                onChange={handleImageChange}
                className="hidden"
                disabled={isStreaming || tokenLimitReached}
              />
            </label>

            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={tokenLimitReached ? "Token limit reached - start a new conversation" : "Describe your dream trip..."}
              className="flex-1 px-4 py-2 bg-input border border-border text-foreground rounded-lg focus:ring-2 focus:ring-primary focus:outline-none transition-all"
              disabled={isStreaming || tokenLimitReached}
            />

            {isStreaming ? (
              <button
                type="button"
                onClick={stopStreaming}
                className="bg-destructive text-destructive-foreground px-4 py-2 rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2 shadow-sm"
              >
                <StopCircle size={20} />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                className="bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                disabled={(!input.trim() && !image) || tokenLimitReached}
              >
                <Send size={20} />
                Send
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default ChatWindow;
