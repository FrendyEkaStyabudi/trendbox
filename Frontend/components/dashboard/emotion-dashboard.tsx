"use client"

import { useEffect, useState } from "react"
import {
  Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle,
} from "@/components/ui/card"
import {
  Tabs, TabsContent, TabsList, TabsTrigger,
} from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import {
  ArrowUpCircle, Camera, Calendar, RefreshCw, TrendingDown,
  TrendingUp, Clock, VideoIcon, BarChart, LineChart, AreaChartIcon, ScanFace, Shirt
} from "lucide-react"
import RealtimeEmotionChart from "../charts/realtime-emotion-chart" // Adjusted path
import EmotionDistributionChart from "../charts/emotion-distribution-chart" // Adjusted path
import RecentEmotionLogsTable from "../tables/recent-emotion-logs-table" // Adjusted path
import { Badge } from "@/components/ui/badge"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"


type AttributeDistribution = {
  label: string
  count: number
}

type AnalyticsMetric = "emotion" | "head" | "clothing"

const metricTitles: Record<AnalyticsMetric, string> = {
  emotion: "Emotion",
  head: "Head Attribute",
  clothing: "Clothing Attribute",
}

type AttributeStats = {
  total: number
  dominant: string
  distribution: AttributeDistribution[]
}

type SummaryResponse = {
  detected_faces: number
  dominant_emotion: string
  weekly_changes: Record<string, number>
  attribute_summary: {
    head: AttributeStats
    clothing: AttributeStats
  }
}

const emptyAttributeStats = (): AttributeStats => ({
  total: 0,
  dominant: "N/A",
  distribution: [],
})

const emptyAttributeSummary = () => ({
  head: emptyAttributeStats(),
  clothing: emptyAttributeStats(),
})

const formatAttributeLabel = (label: string) =>
  label === "N/A"
    ? label
    : label.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())

const emotionColors: Record<string, string> = {
  happy: "bg-yellow-400 text-yellow-900", // Adjusted for better contrast
  sad: "bg-blue-400 text-blue-900",
  angry: "bg-red-500 text-white",
  neutral: "bg-gray-400 text-gray-900",
  surprised: "bg-purple-400 text-purple-900",
  scared: "bg-pink-400 text-pink-900",
  fear: "bg-green-400 text-green-900", // Assuming 'fear' might be 'scared' or another distinct emotion
  disgust: "bg-teal-400 text-teal-900",
  // Add other emotions if present
}

const getEmotionColor = (emotion: string) => {
    return emotionColors[emotion.toLowerCase()] ?? "bg-slate-500 text-white";
}

function AttributeBreakdown({ title, stats }: { title: string; stats: AttributeStats }) {
  const maximum = Math.max(1, ...stats.distribution.map((item) => item.count))

  return (
    <div className="space-y-3 rounded-lg border p-4">
      <div className="flex items-center justify-between gap-3">
        <h4 className="font-medium">{title}</h4>
        <Badge variant="secondary">{stats.total} data</Badge>
      </div>
      {stats.distribution.length === 0 ? (
        <p className="text-sm text-muted-foreground">No attributes detected today.</p>
      ) : (
        <div className="space-y-3">
          {stats.distribution.map((item) => (
            <div key={item.label} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>{formatAttributeLabel(item.label)}</span>
                <span className="font-medium">{item.count}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-purple-500"
                  style={{ width: `${Math.max(5, (item.count / maximum) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}


export default function EmotionDashboard() {
  // const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://dmpkenvfix-1091079456692.asia-southeast2.run.app"
  const API = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:5000"

  const [activeTab, setActiveTab] = useState("overview")
  const [mockVideoFeed, setMockVideoFeed] = useState(true) // Keep if used
  const [summary, setSummary] = useState<SummaryResponse>({
    detected_faces: 0,
    dominant_emotion: "N/A",
    weekly_changes: {},
    attribute_summary: emptyAttributeSummary(),
  })

  // State for Emotion Distribution Chart
  const [distributionRange, setDistributionRange] = useState<"today" | "week" | "month">("today");
  const [distributionMetric, setDistributionMetric] = useState<AnalyticsMetric>("emotion");

  // State for Real-Time Emotion Trends Chart
  const [realtimeTrendChartType, setRealtimeTrendChartType] = useState<"line" | "bar" | "area">("line");
  const [trendMetric, setTrendMetric] = useState<AnalyticsMetric>("emotion");

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API}/api/summary`)
      if (!res.ok) throw new Error(`API Error: ${res.status}`)
      const data: Partial<SummaryResponse> = await res.json()
      setSummary({
        detected_faces: data.detected_faces ?? 0,
        dominant_emotion: data.dominant_emotion ?? "N/A",
        weekly_changes: data.weekly_changes ?? {},
        attribute_summary: data.attribute_summary ?? emptyAttributeSummary(),
      })
    } catch (err) {
      console.error("Error fetching summary:", err)
      // Optionally set summary to default error state
      setSummary({
        detected_faces: 0,
        dominant_emotion: "Error",
        weekly_changes: {},
        attribute_summary: emptyAttributeSummary(),
      });
    }
  }

  useEffect(() => {
    fetchSummary()
    const id = setInterval(fetchSummary, 60_000) // Refresh summary every 60 seconds
    return () => clearInterval(id)
  }, [API]) // Add API to dependency array if it could change, though unlikely for env var

  return (
    <div className="w-full max-w-full space-y-6 overflow-x-hidden">
      {/* ==== KPI Row ==== */}
      <div className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {/* Detected faces */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Detected Faces Today</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary.detected_faces}</div>
            <p className="text-xs text-muted-foreground">
              {/* Placeholder for comparison, e.g., +15% from yesterday */}
              Real-time updates
            </p>
          </CardContent>
        </Card>

        {/* Dominant emotion */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Dominant Emotion</CardTitle>
            {/* Use an icon that fits, e.g. Smile or Frown based on emotion? Or a generic one */}
            <ArrowUpCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center space-x-2">
              <div className="text-2xl font-bold capitalize">
                {summary.dominant_emotion}
              </div>
              {summary.dominant_emotion !== "N/A" && summary.dominant_emotion !== "Error" && (
                <Badge
                  className={`${getEmotionColor(summary.dominant_emotion)}`}
                >
                  Live
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">Updated just now</p>
          </CardContent>
        </Card>

        {/* Dominant head attribute */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Dominant Head Attribute</CardTitle>
            <ScanFace className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatAttributeLabel(summary.attribute_summary.head.dominant)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary.attribute_summary.head.total} head attributes today
            </p>
          </CardContent>
        </Card>

        {/* Dominant clothing attribute */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Dominant Clothing</CardTitle>
            <Shirt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatAttributeLabel(summary.attribute_summary.clothing.dominant)}
            </div>
            <p className="text-xs text-muted-foreground">
              {summary.attribute_summary.clothing.total} clothing attributes today
            </p>
          </CardContent>
        </Card>

        {/* Weekly change */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium">Weekly Emotion Change</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="max-h-32 overflow-y-auto"> {/* Added for scroll if many emotions */}
            {Object.keys(summary.weekly_changes).length === 0 ? (
              <p className="text-sm text-muted-foreground">No data for comparison</p>
            ) : (
              Object.entries(summary.weekly_changes)
                .sort(([, changeA], [, changeB]) => Math.abs(changeB) - Math.abs(changeA)) // Sort by magnitude of change
                .map(([emotion, change]) => (
                  <div key={emotion} className="text-xs text-muted-foreground flex items-center capitalize">
                    {change >= 0 ? (
                      <TrendingUp className="inline h-3 w-3 mr-1 text-green-500 flex-shrink-0" />
                    ) : (
                      <TrendingDown className="inline h-3 w-3 mr-1 text-red-500 flex-shrink-0" />
                    )}
                    <span className="font-semibold mr-1">{emotion}:</span>
                    <span>{change.toFixed(1)}%</span>
                  </div>
                ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* ==== Tabs ==== */}
      <Tabs
        defaultValue="overview"
        className="space-y-4"
        onValueChange={setActiveTab}
        value={activeTab}
      >
        <div className="flex flex-col items-stretch justify-between gap-2 sm:flex-row sm:items-center">
          <TabsList className="h-auto w-full flex-wrap justify-start sm:w-auto">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="realtime" disabled>Real-time View</TabsTrigger> {/* Assuming this is WIP based on image */}
            <TabsTrigger value="trends">Trend Analysis</TabsTrigger>
          </TabsList>

          <Button variant="outline" size="sm" onClick={fetchSummary}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh Data
          </Button>
        </div>

        {/* ===== Overview Tab ===== */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2"> {/* Changed lg:grid-cols-4 to md:grid-cols-2 for better fit */}
            <Card className="col-span-1 md:col-span-1"> {/* Adjusted span */}
              <CardHeader>
                <div className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
                  <div className="space-y-2">
                    <CardTitle>{metricTitles[distributionMetric]} Distribution</CardTitle>
                    <Select value={distributionMetric} onValueChange={(value) => setDistributionMetric(value as AnalyticsMetric)}>
                      <SelectTrigger className="h-8 w-full min-w-[180px] sm:w-[180px]"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="emotion">Emotion</SelectItem>
                        <SelectItem value="head">Head Attribute</SelectItem>
                        <SelectItem value="clothing">Clothing Attribute</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <ToggleGroup 
                    type="single" 
                    defaultValue="today" 
                    size="sm" 
                    value={distributionRange}
                    onValueChange={(value) => { if (value) setDistributionRange(value as "today" | "week" | "month")}}
                  >
                    <ToggleGroupItem value="today" aria-label="Today">Today</ToggleGroupItem>
                    <ToggleGroupItem value="week" aria-label="This Week">This Week</ToggleGroupItem>
                    <ToggleGroupItem value="month" aria-label="This Month">This Month</ToggleGroupItem>
                  </ToggleGroup>
                </div>
              </CardHeader>
              <CardContent className="pl-2">
                <EmotionDistributionChart range={distributionRange} metric={distributionMetric} />
              </CardContent>
            </Card>

            <Card className="col-span-1 md:col-span-1"> {/* Adjusted span */}
              <CardHeader>
                 <div className="flex flex-col items-start justify-between gap-2 sm:flex-row sm:items-center">
                  <div className="space-y-2">
                    <CardTitle>Real-Time {metricTitles[trendMetric]} Trends</CardTitle>
                    <Select value={trendMetric} onValueChange={(value) => setTrendMetric(value as AnalyticsMetric)}>
                      <SelectTrigger className="h-8 w-full min-w-[180px] sm:w-[180px]"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="emotion">Emotion</SelectItem>
                        <SelectItem value="head">Head Attribute</SelectItem>
                        <SelectItem value="clothing">Clothing Attribute</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                   <ToggleGroup 
                    type="single" 
                    defaultValue="line" 
                    size="sm"
                    value={realtimeTrendChartType}
                    onValueChange={(value) => { if (value) setRealtimeTrendChartType(value as "line" | "bar" | "area")}}
                  >
                    <ToggleGroupItem value="area" aria-label="Area chart"><AreaChartIcon className="h-4 w-4"/></ToggleGroupItem>
                    <ToggleGroupItem value="line" aria-label="Line chart"><LineChart className="h-4 w-4"/></ToggleGroupItem>
                    <ToggleGroupItem value="bar" aria-label="Bar chart"><BarChart className="h-4 w-4"/></ToggleGroupItem>
                  </ToggleGroup>
                </div>
              </CardHeader>
              <CardContent className="pl-2">
                {/* This instance is for today's hourly trends */}
                <RealtimeEmotionChart chartType={realtimeTrendChartType} weekly={false} metric={trendMetric} /> 
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Attribute Distribution Today</CardTitle>
              <CardDescription>
                Head and clothing attribute summary from today's realtime tracking results.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <AttributeBreakdown title="Head Attributes" stats={summary.attribute_summary.head} />
              <AttributeBreakdown title="Clothing Attributes" stats={summary.attribute_summary.clothing} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Emotion Logs</CardTitle>
              <CardDescription>Last 50 emotion events recorded.</CardDescription>
            </CardHeader>
            <CardContent>
              <RecentEmotionLogsTable />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== Realâ€‘time Tab (Placeholder based on your existing structure) ===== */}
        <TabsContent value="realtime" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="md:col-span-2">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle>Live Camera Feed</CardTitle>
                <div className="flex items-center space-x-2">
                  <Badge variant="outline" className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> Low Latency 120ms
                  </Badge>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setMockVideoFeed(!mockVideoFeed)}
                  >
                    <VideoIcon className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="relative aspect-video bg-muted rounded-md overflow-hidden border">
                  {mockVideoFeed ? (
                    <div className="absolute inset-0 flex items-center justify-center opacity-60">
                      <Camera className="h-12 w-12 text-slate-400" />
                    </div>
                  ) : (
                    <img
                      // src="/placeholder.svg?height=400&width=800" // Replace with actual feed or placeholder
                      src="https://via.placeholder.com/800x450.png/333333/FFFFFF?text=Live+Feed+Paused"
                      alt="Video placeholder"
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Camera Setup</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">Camera configuration options will appear here.</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ===== Trends Tab ===== */}
        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div>
                  <CardTitle>Weekly {metricTitles[trendMetric]} Trends</CardTitle>
                  <CardDescription>Day-by-day trends for the current week.</CardDescription>
                </div>
                <Select value={trendMetric} onValueChange={(value) => setTrendMetric(value as AnalyticsMetric)}>
                  <SelectTrigger className="w-full sm:w-[180px]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="emotion">Emotion</SelectItem>
                    <SelectItem value="head">Head Attribute</SelectItem>
                    <SelectItem value="clothing">Clothing Attribute</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardHeader>
            <CardContent className="pl-2">
              {/* This instance is for weekly (daily data for current week) trends, default to line chart */}
              <RealtimeEmotionChart weekly chartType="line" metric={trendMetric} /> 
            </CardContent>
          </Card>
           {/* You could add another chart here for historical daily trends using /api/trends endpoint */}
           {/*
           <Card>
            <CardHeader>
              <CardTitle>Historical Daily Trends</CardTitle>
            </CardHeader>
            <CardContent className="pl-2">
              <RealtimeEmotionChart weekly={false} historical={true} chartType="line" /> 
            </CardContent>
          </Card>
          */}
        </TabsContent>
      </Tabs>
    </div>
  )
}
