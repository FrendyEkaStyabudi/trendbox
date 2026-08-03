"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { addDays, format, startOfDay } from "date-fns"
import { BarChart2, CalendarIcon, RefreshCcw, TrendingUp, X } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import ForecastChart from "../charts/forecast-chart"
import EmotionComparisonChart from "../charts/emotion-comparison-chart"

export interface ApiForecastDataPoint {
  name: string
  yhat: number | null
  yhat_lower?: number | null
  yhat_upper?: number | null
  actual?: number | null
}

type ForecastKind = "emotion" | "head" | "clothing"

type ForecastOptions = Record<ForecastKind, string[]>

type ForecastSummary = {
  accuracies: Record<string, number | string>
  trends: Record<string, string>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:5000"

const DEFAULT_OPTIONS: ForecastOptions = {
  emotion: ["angry", "fear", "happy", "sad", "surprised"],
  head: ["hair", "hat", "hijab"],
  clothing: ["blouse", "long_pants", "outer", "shirt", "shorts", "skirt", "sweater", "t-shirt"],
}

const KIND_LABELS: Record<ForecastKind, string> = {
  emotion: "Emotion",
  head: "Head Attribute",
  clothing: "Clothing Attribute",
}

const formatLabel = (value: string) =>
  value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())

export default function ForecastingPage() {
  const [options, setOptions] = useState<ForecastOptions>(DEFAULT_OPTIONS)
  const [dataType, setDataType] = useState<ForecastKind>("emotion")
  const [selectedLabel, setSelectedLabel] = useState("happy")
  const [comparisonLabels, setComparisonLabels] = useState<string[]>(["happy", "sad"])
  const [startDate, setStartDate] = useState<Date>(() => startOfDay(addDays(new Date(), -30)))
  const [endDate, setEndDate] = useState<Date>(() => startOfDay(addDays(new Date(), 7)))
  const [forecastDays, setForecastDays] = useState("7")
  const [timelineData, setTimelineData] = useState<ApiForecastDataPoint[]>([])
  const [comparisonData, setComparisonData] = useState<Record<string, ApiForecastDataPoint[]>>({})
  const [summary, setSummary] = useState<ForecastSummary | null>(null)
  const [loadingTimeline, setLoadingTimeline] = useState(false)
  const [loadingComparison, setLoadingComparison] = useState(false)
  const [loadingSummary, setLoadingSummary] = useState(false)

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/forecast/options`)
      .then((response) => {
        if (!response.ok) throw new Error(`Options API error: ${response.status}`)
        return response.json()
      })
      .then((data: Partial<ForecastOptions>) => {
        setOptions({
          emotion: data.emotion?.length ? data.emotion : DEFAULT_OPTIONS.emotion,
          head: data.head?.length ? data.head : DEFAULT_OPTIONS.head,
          clothing: data.clothing?.length ? data.clothing : DEFAULT_OPTIONS.clothing,
        })
      })
      .catch((error) => console.error("Failed to load forecast options:", error))
  }, [])

  useEffect(() => {
    const labels = options[dataType]
    const preferred = dataType === "emotion" && labels.includes("happy") ? "happy" : labels[0]
    setSelectedLabel(preferred)
    setComparisonLabels(labels.slice(0, 2))
    setTimelineData([])
    setComparisonData({})
  }, [dataType, options])

  const requestForecast = useCallback(
    async (label: string): Promise<ApiForecastDataPoint[]> => {
      const response = await fetch(`${API_BASE_URL}/api/forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data_type: dataType,
          label,
          emotion: label,
          forecast_days: Number(forecastDays),
          granularity: "daily",
          start_date: format(startDate, "yyyy-MM-dd"),
          end_date: format(endDate, "yyyy-MM-dd"),
        }),
      })
      if (!response.ok) {
        const details = await response.text()
        throw new Error(`Forecast API error ${response.status}: ${details}`)
      }
      const data = await response.json()
      return data.forecast_points ?? []
    },
    [dataType, forecastDays, startDate, endDate]
  )

  const fetchTimeline = useCallback(async () => {
    if (!selectedLabel) return
    setLoadingTimeline(true)
    try {
      setTimelineData(await requestForecast(selectedLabel))
    } catch (error) {
      console.error("Failed to load timeline forecast:", error)
      setTimelineData([])
    } finally {
      setLoadingTimeline(false)
    }
  }, [requestForecast, selectedLabel])

  const fetchComparison = useCallback(async () => {
    setLoadingComparison(true)
    try {
      const entries = await Promise.all(
        comparisonLabels.map(async (label) => [label, await requestForecast(label)] as const)
      )
      setComparisonData(Object.fromEntries(entries))
    } catch (error) {
      console.error("Failed to load comparison forecast:", error)
      setComparisonData({})
    } finally {
      setLoadingComparison(false)
    }
  }, [comparisonLabels, requestForecast])

  const fetchSummary = useCallback(async () => {
    setLoadingSummary(true)
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/forecast_summary?data_type=${encodeURIComponent(dataType)}`
      )
      if (!response.ok) throw new Error(`Summary API error: ${response.status}`)
      setSummary(await response.json())
    } catch (error) {
      console.error("Failed to load forecast summary:", error)
      setSummary(null)
    } finally {
      setLoadingSummary(false)
    }
  }, [dataType])

  useEffect(() => {
    void fetchTimeline()
    void fetchSummary()
  }, [fetchTimeline, fetchSummary])

  useEffect(() => {
    void fetchComparison()
  }, [fetchComparison])

  const accuracy = summary?.accuracies?.[selectedLabel]
  const trend = summary?.trends?.[selectedLabel] ?? "N/A"
  const availableLabels = options[dataType]
  const remainingLabels = availableLabels.filter((label) => !comparisonLabels.includes(label))
  const hasComparisonData = useMemo(
    () => comparisonLabels.some((label) => comparisonData[label]?.length),
    [comparisonData, comparisonLabels]
  )

  const refreshAll = () => {
    void fetchTimeline()
    void fetchComparison()
    void fetchSummary()
  }

  return (
    <div className="w-full max-w-full space-y-6 overflow-x-hidden">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">Analytics Forecasting</h1>
          <p className="text-muted-foreground">
            Forecast emotion, head, and clothing activity from tracked data.
          </p>
        </div>
        <Button variant="outline" className="w-full sm:w-auto" onClick={refreshAll}>
          <RefreshCcw className="mr-2 h-4 w-4" /> Refresh Forecast
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Data Type</CardTitle>
            <BarChart2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{KIND_LABELS[dataType]}</div>
            <p className="text-xs text-muted-foreground">{formatLabel(selectedLabel)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Forecast Accuracy</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loadingSummary ? "..." : typeof accuracy === "number" ? `${accuracy.toFixed(1)}%` : accuracy ?? "N/A"}
            </div>
            <p className="text-xs text-muted-foreground">Historical fit estimate</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Weekly Trend</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loadingSummary ? "..." : trend}</div>
            <p className="text-xs text-muted-foreground">Latest week versus previous week</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Forecast Configuration</CardTitle></CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <div className="space-y-2">
            <label className="text-sm font-medium">Data Type</label>
            <Select value={dataType} onValueChange={(value) => setDataType(value as ForecastKind)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="emotion">Emotion</SelectItem>
                <SelectItem value="head">Head Attribute</SelectItem>
                <SelectItem value="clothing">Clothing Attribute</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Selected Label</label>
            <Select value={selectedLabel} onValueChange={setSelectedLabel}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {availableLabels.map((label) => (
                  <SelectItem key={label} value={label}>{formatLabel(label)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Forecast Horizon</label>
            <Select value={forecastDays} onValueChange={setForecastDays}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="7">7 days</SelectItem>
                <SelectItem value="14">14 days</SelectItem>
                <SelectItem value="30">30 days</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DatePicker label="Start Date" value={startDate} onChange={(date) => date && setStartDate(date)} />
          <DatePicker label="End Date" value={endDate} onChange={(date) => date && setEndDate(date)} />
        </CardContent>
      </Card>

      <Tabs defaultValue="timeline" className="space-y-4">
        <TabsList className="h-auto w-full flex-wrap justify-start sm:w-auto">
          <TabsTrigger value="timeline">Timeline Forecast</TabsTrigger>
          <TabsTrigger value="comparison">Label Comparison</TabsTrigger>
        </TabsList>

        <TabsContent value="timeline">
          <Card>
            <CardHeader>
              <CardTitle>{KIND_LABELS[dataType]} Forecast: {formatLabel(selectedLabel)}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[320px] sm:h-[400px]">
                {loadingTimeline ? (
                  <div className="flex h-full items-center justify-center text-muted-foreground">Loading forecast...</div>
                ) : timelineData.length ? (
                  <ForecastChart chartData={timelineData} emotion={selectedLabel} />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    No tracked data is available for this label and period.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="comparison">
          <Card>
            <CardHeader className="flex flex-col items-start justify-between gap-3 sm:flex-row sm:items-center">
              <CardTitle>{KIND_LABELS[dataType]} Comparison</CardTitle>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="sm" disabled={!remainingLabels.length || comparisonLabels.length >= 5}>
                    Add Label ({comparisonLabels.length}/5)
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[min(220px,calc(100vw-2rem))] p-2">
                  {remainingLabels.slice(0, 10).map((label) => (
                    <Button
                      key={label}
                      variant="ghost"
                      className="w-full justify-start"
                      onClick={() => setComparisonLabels((current) => [...current, label].slice(0, 5))}
                    >
                      {formatLabel(label)}
                    </Button>
                  ))}
                </PopoverContent>
              </Popover>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex flex-wrap gap-2">
                {comparisonLabels.map((label) => (
                  <div key={label} className="flex items-center rounded-full bg-muted px-3 py-1 text-sm">
                    <span className="mr-2">{formatLabel(label)}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 rounded-full"
                      onClick={() => setComparisonLabels((current) => current.filter((item) => item !== label))}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="h-[320px] sm:h-[400px]">
                {loadingComparison ? (
                  <div className="flex h-full items-center justify-center text-muted-foreground">Loading comparison...</div>
                ) : hasComparisonData ? (
                  <EmotionComparisonChart multiEmotionData={comparisonData} />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    Select labels with tracked data to compare forecasts.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function DatePicker({
  label,
  value,
  onChange,
}: {
  label: string
  value: Date
  onChange: (date?: Date) => void
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" className={cn("w-full justify-start text-left font-normal")}>
            <CalendarIcon className="mr-2 h-4 w-4" />
            {format(value, "PPP")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar mode="single" selected={value} onSelect={onChange} initialFocus />
        </PopoverContent>
      </Popover>
    </div>
  )
}
