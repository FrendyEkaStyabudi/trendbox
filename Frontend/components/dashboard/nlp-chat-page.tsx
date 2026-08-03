// components/dashboard/nlp-chat-page.tsx

"use client"

import { useState, useRef, useEffect, FormEvent } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Send, Bot, User, Clock, RefreshCw, BarChart, ChevronRight, Download } from "lucide-react"
import ReactMarkdown, { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChatSettings } from "./ChatSettings"
import { EmotionChart, isDataChartable } from "./EmotionChart"

// --- Interface dan Konstanta (Tidak Berubah) ---
interface ChatMessage {
  id: string
  sender: "user" | "bot"
  text: string
  hasChart?: boolean
  timestamp: Date
  generatedSQL?: string | null
  reasoning?: string | null
  queryResult?: any[] | null
  errorMessage?: string | null
  infoMessage?: string | null
  originalUserQuery?: string;
}

const QUICK_QUESTIONS = [
  "What was the most common emotion yesterday?",
  "Show me the trend for happy emotions last week.",
  "How much total data for 7 day?",
  "how much emotion happy in this week",
  "How many 'sad' emotions were recorded today?",
  "List 5 recent 'angry' emotions."
]

interface BackendResponse {
  original_prompt: string;
  generated_sql: string | null;
  reasoning: string | null;
  query_result: any[] | null;
  error_message: string | null;
  info_message: string | null;
  has_chart_data: boolean;
}

interface NlpChatPageProps {
  currentUser: any; 
}


// --- Komponen Utama ---
export default function NlpChatPage({ currentUser }: NlpChatPageProps) {
  // --- State dan Hooks (Tidak Berubah) ---
  const [message, setMessage] = useState("")
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      sender: "bot",
      text: currentUser 
        ? "Hello! I'm your emotion analytics assistant. How can I help you today?"
        : "Hello! I'm your emotion analytics assistant. Please log in to access chatbot settings and advanced features.",
      timestamp: new Date(Date.now() - 60000),
    },
  ])
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // --- Functions (Tidak Berubah) ---
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [chatMessages])

  const handleSendMessage = async (textParam?: string) => {
    const currentQueryText = (typeof textParam === 'string' ? textParam : message).trim();
    if (!currentQueryText) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: currentQueryText,
      timestamp: new Date(),
    }

    setChatMessages((prev) => [...prev, userMessage])
    if (typeof textParam !== 'string') {
        setMessage("")
    }
    setIsTyping(true)

    try {
//       const response = await fetch("https://chatbot-1091079456692.asia-southeast2.run.app/api/chat", {
const response = await fetch(`${process.env.NEXT_PUBLIC_NLP_API_BASE_URL ?? "http://127.0.0.1:5003"}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: currentQueryText }),
      });

      const backendData: BackendResponse = await response.json();

      if (!response.ok) {
        throw new Error(backendData.error_message || `HTTP error! status: ${response.status}`);
      }

      let botTextResponse = "";
      if (backendData.error_message) {
        botTextResponse = `š ï¸ **Error:**\n${backendData.error_message}`;
        if (backendData.generated_sql) {
            botTextResponse += `\n\nðŸ” **Generated SQL (failed execution):**\n\`\`\`sql\n${backendData.generated_sql}\n\`\`\``;
        }
      } else {
        botTextResponse = backendData.reasoning ? `ðŸ¤” **Reasoning:**\n${backendData.reasoning}` : "I've processed your request.";
        if (backendData.generated_sql) {
          botTextResponse += `\n\nðŸ” **Generated SQL:**\n\`\`\`sql\n${backendData.generated_sql}\n\`\`\``;
        }
        if (backendData.query_result && backendData.query_result.length > 0) {
          botTextResponse += `\n\nðŸ“Š **Query Result (Preview):**\n\`\`\`json\n${JSON.stringify(backendData.query_result.slice(0, 5), null, 2)}\n\`\`\``;
          if (backendData.query_result.length > 5) {
            botTextResponse += `\n*(Showing 5 of ${backendData.query_result.length} records.)*`;
          }
        } else if (backendData.info_message) {
            botTextResponse += `\n\n„¹ï¸ **Info:** ${backendData.info_message}`;
        }
      }

      // Remove legacy mojibake prefixes that were stored before the project
      // source files were normalized to UTF-8. Keep the Markdown headings.
      botTextResponse = botTextResponse.replace(
        /^[^*\r\n]*(?=\*\*(?:Error|Generated SQL(?: \(failed execution\))?|Reasoning|Query Result \(Preview\)|Info):\*\*)/gm,
        "",
      );

      const botMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "bot",
        text: botTextResponse,
        hasChart: backendData.has_chart_data || false,
        timestamp: new Date(),
        generatedSQL: backendData.generated_sql,
        reasoning: backendData.reasoning,
        queryResult: backendData.query_result,
        errorMessage: backendData.error_message,
        infoMessage: backendData.info_message,
        originalUserQuery: currentQueryText,
      };
      setChatMessages((prev) => [...prev, botMessage]);

    } catch (error: any) {
      console.error("Error sending message or processing response:", error);
      const errorBotMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "bot",
        text: `š ï¸ **An error occurred:**\n${error.message || "Failed to get response from assistant."}`,
        timestamp: new Date(),
        errorMessage: error.message || "Failed to get response from assistant.",
        originalUserQuery: currentQueryText,
      };
      setChatMessages((prev) => [...prev, errorBotMessage]);
    } finally {
      setIsTyping(false);
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  const handleDownloadChartData = (data: any[] | null | undefined, queryFileNamePart: string | undefined) => {
    if (!data || data.length === 0) return;
    const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
      JSON.stringify(data, null, 2)
    )}`;
    const link = document.createElement("a");
    link.href = jsonString;
    const safeQueryName = (queryFileNamePart || "export").replace(/[^a-z0-9]/gi, '_').toLowerCase().slice(0,30);
    link.download = `emotion_data_${safeQueryName}.json`;
    link.click();
  };

  const markdownComponents: Components = {
    code({ node, inline, className, children, ...props }: { node?: any; inline?: boolean; className?: string; children?: React.ReactNode; [key: string]: any; }) {
      const match = /language-(\w+)/.exec(className || '');
      return !inline && match ? (
        <div className="my-2 bg-muted/70 dark:bg-muted/40 p-2 rounded text-xs overflow-x-auto border">
          <pre><code className={className} {...props}>{String(children).replace(/\n$/, '')}</code></pre>
        </div>
      ) : ( <code className="bg-muted dark:bg-muted/70 px-1 py-0.5 rounded text-xs" {...props}>{children}</code> );
    },
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    handleSendMessage();
  }

// --- [PERBAIKAN UTAMA DI SINI] ---
// Pastikan struktur return Anda sama persis seperti ini.
return (
    // 1. DIV PEMBUNGKUS UTAMA: Harus punya `grid` dan `md:grid-cols-5` untuk membuat 2 kolom di desktop.
    <div className="grid h-[calc(100svh-7rem)] min-h-[560px] min-w-0 grid-cols-1 gap-4 md:h-[calc(100svh-9rem)] md:grid-cols-5">
      
      {/* 2. KOLOM KIRI (CHAT): Harus punya `md:col-span-3` untuk mengambil 3 dari 5 bagian kolom. */}
      <Card className="flex min-w-0 flex-col h-full md:col-span-3">
        <CardHeader>
          <div className="flex flex-col items-start justify-between gap-3 sm:flex-row">
            <div className="min-w-0">
              <CardTitle className="flex items-center gap-2"><Bot className="h-6 w-6 text-primary"/> AI SQL Assistant</CardTitle>
              <CardDescription>Ask questions about emotion data using natural language</CardDescription>
            </div>
            <div className="flex shrink-0 items-center space-x-2">
              <Badge variant="outline" className="flex items-center gap-1"><Clock className="h-3 w-3" /><span>Real-time</span></Badge>
              <Button variant="ghost" size="icon" onClick={() => window.location.reload()} title="Refresh Chat"><RefreshCw className="h-4 w-4" /></Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col overflow-hidden p-0">
          <div className="flex-1 overflow-y-auto px-4 py-2 space-y-4">
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`flex min-w-0 gap-3 max-w-[95%] md:max-w-[80%] ${msg.sender === "user" ? "flex-row-reverse" : ""}`}>
                  <Avatar className={`h-8 w-8 flex-shrink-0 ${msg.sender === "user" ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
                    <AvatarFallback>{msg.sender === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 space-y-1 w-full">
                    <div className={`rounded-lg p-3 text-sm ${msg.sender === "user" ? "bg-primary text-primary-foreground" : (msg.errorMessage ? "bg-destructive/20 border border-destructive/50" : "bg-muted")}`}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.text}</ReactMarkdown>
                    </div>

                    {msg.sender === "bot" &&
                      msg.hasChart &&
                      msg.queryResult &&
                      msg.queryResult.length > 0 &&
                      isDataChartable(msg.queryResult) && (
                        <div className="mt-2 max-w-full overflow-x-auto rounded-lg border bg-card p-3 shadow">
                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm font-medium mb-2">
                              <span className="flex items-center gap-1"><BarChart className="h-4 w-4"/>Emotion Data Visualization</span>
                              <Button variant="outline" size="sm" className="h-7 px-2 py-1 text-xs" onClick={() => handleDownloadChartData(msg.queryResult, msg.originalUserQuery)}><Download className="h-3 w-3 mr-1" />Data</Button>
                            </div>
                            <EmotionChart data={msg.queryResult} />
                          </div>
                        </div>
                      )}

                    <div className="text-xs text-muted-foreground pt-1">{formatTime(msg.timestamp)}</div>
                  </div>
                </div>
              </div>
            ))}
            {isTyping && ( <div className="flex justify-start"><div className="flex gap-3 max-w-[80%]"><Avatar className="h-8 w-8 bg-muted flex-shrink-0"><AvatarFallback><Bot className="h-4 w-4" /></AvatarFallback></Avatar><div className="space-y-1"><div className="rounded-lg p-3 bg-muted flex items-center gap-1.5 h-8"><Skeleton className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce" /><Skeleton className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce delay-200" /><Skeleton className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-bounce delay-400" /></div></div></div></div> )}
            <div ref={messagesEndRef} />
          </div>
          <div className="border-t p-3 md:p-4">
            <form onSubmit={handleSubmit} className="flex gap-2 items-center">
              <Input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Ask a question about emotion data..." className="flex-1 h-10" onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }}} />
              <Button type="submit" size="icon" className="h-10 w-10 flex-shrink-0" disabled={isTyping || !message.trim()}><Send className="h-4 w-4" /></Button>
            </form>
          </div>
        </CardContent>
      </Card>

      {/* 3. KOLOM KANAN (SETTINGS & QUICK QUESTIONS): Harus punya `md:col-span-2` untuk mengambil 2 sisa kolom. */}
      <div className="min-w-0 flex flex-col gap-4 md:col-span-2">
        {currentUser && <ChatSettings />}
        
        <Card className="flex-col h-full hidden md:flex flex-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ChevronRight className="h-5 w-5 text-muted-foreground"/> Quick Questions</CardTitle>
            <CardDescription>Examples to get you started.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto">
            <div className="space-y-2">
              {QUICK_QUESTIONS.map((question, index) => (
                <Button key={index} variant="outline" className="w-full justify-start text-left h-auto py-2.5 px-3 text-sm hover:bg-accent/50" onClick={() => { setMessage(question); handleSendMessage(question); }} disabled={isTyping || !currentUser}>
                  <ChevronRight className="mr-2 h-4 w-4 flex-shrink-0 text-primary" />
                  <span className="line-clamp-2">{question}</span>
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

    </div>
  )
}
