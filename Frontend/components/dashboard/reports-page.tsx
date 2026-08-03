"use client";

import { useState, useMemo, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalendarIcon, Download } from "lucide-react";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import EmotionDistributionChart from "../charts/emotion-distribution-chart";
import ForecastChart from "../charts/forecast-chart";

// Tipe data untuk komponen ForecastChart
export interface ApiForecastDataPoint {
  name: string;
  actual: number | null;
  yhat: number | null;
  yhat_lower: number | null;
  yhat_upper: number | null;
}

// Tipe data untuk laporan utama dari API
interface ReportData {
  reportMetadata: {
    reportTitle: string;
    dateRangeFormatted: string;
    generatedAt: string;
  };
  charts?: {
    emotionTrends?: {
      categories: string[];
      series: { name: string; data: number[]; }[];
    };
    attributeDistribution?: {
      head: { label: string; count: number }[];
      clothing: { label: string; count: number }[];
    };
  };
  tables?: {
    dailySummary?: { date: string; [key: string]: any; }[];
    attributeSummary?: { type: string; label: string; count: number }[];
  };
  insights?: {
    badge: string; color: string; title: string; description: string;
  }[];
}

const ALL_EMOTIONS = ["happy", "sad", "angry", "neutral", "surprised"];

const formatAttributeLabel = (label: string) =>
  label.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

function AttributeDistributionSummary({
  data,
}: {
  data: NonNullable<NonNullable<ReportData["charts"]>["attributeDistribution"]>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Attribute Distribution</CardTitle>
        <CardDescription>Head and clothing attributes detected in the selected period</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        {(["head", "clothing"] as const).map((type) => {
          const items = data[type] ?? [];
          const maximum = Math.max(1, ...items.map((item) => item.count));
          return (
            <div key={type} className="space-y-3 rounded-lg border p-4">
              <div className="flex items-center justify-between">
                <h4 className="font-medium capitalize">{type} Attributes</h4>
                <Badge variant="secondary">{items.reduce((sum, item) => sum + item.count, 0)} data</Badge>
              </div>
              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground">No {type} attributes found.</p>
              ) : (
                items.map((item) => (
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
                ))
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export default function ReportsPage() {
  const [date, setDate] = useState<Date | undefined>(undefined);
  const [endDate, setEndDate] = useState<Date | undefined>(undefined);
  const [selectedEmotions, setSelectedEmotions] = useState<string[]>(ALL_EMOTIONS);
  const [generatedReport, setGeneratedReport] = useState(false);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [distributionRange, setDistributionRange] = useState<'today' | 'week' | 'month'>('week');
  const [selectedEmotionForTrend, setSelectedEmotionForTrend] = useState<string>('happy');

  useEffect(() => {
    const today = new Date();
    const previousWeek = new Date();
    previousWeek.setDate(today.getDate() - 7);
    setDate(previousWeek);
    setEndDate(today);
  }, []);

  const handleEmotionChange = (emotion: string, checked: boolean) => {
    setSelectedEmotions(prev =>
      checked ? [...prev, emotion] : prev.filter(e => e !== emotion)
    );
  };

  const handleGenerateReport = async () => {
    if (!date || !endDate) {
        alert("Please select both a start and end date.");
        return;
    }
    setIsLoading(true);
    setGeneratedReport(false);
    const reportConfig = {
      emotions: selectedEmotions,
      dateRange: { start: date.toISOString(), end: endDate.toISOString() },
    };

    try {
      // const response = await fetch("https://report-1091079456692.asia-southeast2.run.app/api/reports", {
      const response = await fetch(`${process.env.NEXT_PUBLIC_REPORT_API_BASE_URL ?? "http://127.0.0.1:5002"}/api/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reportConfig),
      });
      if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
      
      const data: ReportData = await response.json();
      setReportData(data);
      if (data.charts?.emotionTrends?.series?.length) {
        setSelectedEmotionForTrend(data.charts.emotionTrends.series[0].name.toLowerCase());
      }
      setGeneratedReport(true);
    } catch (error) {
      console.error("Failed to generate report:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    if (!date || !endDate) {
        alert("Please select a date range to export.");
        return;
    }
      const exportConfig = {
      emotions: selectedEmotions,
      dateRange: { start: date.toISOString(), end: endDate.toISOString() },
    };
    try {
      // const response = await fetch("https://report-1091079456692.asia-southeast2.run.app/api/export", {
      const response = await fetch(`${process.env.NEXT_PUBLIC_REPORT_API_BASE_URL ?? "http://127.0.0.1:5002"}/api/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(exportConfig),
      });
      if (!response.ok) throw new Error("Export failed");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "emotion_report.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to export report:", error);
    }
  };

  const transformedTrendData = useMemo((): ApiForecastDataPoint[] => {
    const series = reportData?.charts?.emotionTrends?.series;
    const categories = reportData?.charts?.emotionTrends?.categories;
    if (!series || !categories) return [];
    const selectedSeries = series.find(s => s.name.toLowerCase() === selectedEmotionForTrend.toLowerCase());
    if (!selectedSeries) return [];
    return categories.map((date, index) => ({
      name: date, yhat: selectedSeries.data[index],
      actual: null, yhat_lower: null, yhat_upper: null,
    }));
  }, [reportData, selectedEmotionForTrend]);

  const defaultTab = useMemo(() => {
    if (!reportData) return "charts"; // Fallback default
    const attributeDistribution = reportData.charts?.attributeDistribution;
    const hasAttributes = Boolean(attributeDistribution?.head?.length || attributeDistribution?.clothing?.length);
    if (reportData.charts?.emotionTrends?.series?.length || hasAttributes) return "charts";
    if (reportData.tables?.dailySummary?.length || reportData.tables?.attributeSummary?.length) return "tables";
    if (reportData.insights?.length) return "insights";
    return "charts";
  }, [reportData]);

  const attributeDistribution = reportData?.charts?.attributeDistribution;
  const hasEmotionCharts = Boolean(reportData?.charts?.emotionTrends?.series?.length);
  const hasAttributeCharts = Boolean(
    attributeDistribution?.head?.length || attributeDistribution?.clothing?.length
  );
  const hasTables = Boolean(
    reportData?.tables?.dailySummary?.length || reportData?.tables?.attributeSummary?.length
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:space-y-0 md:space-x-4 md:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Emotion Insights & Reports</h2>
          <p className="text-muted-foreground">Generate detailed reports and insights from emotion, head, and clothing data</p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleExport} disabled={!generatedReport || isLoading}>
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Report Configuration</CardTitle>
          <CardDescription>Select your parameters to generate a new report</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label>Date Range</Label>
              <div className="grid grid-cols-2 gap-2">
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant={"outline"} className={cn("w-full justify-start text-left font-normal", !date && "text-muted-foreground")}>
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {date ? format(date, "PPP") : <span>Start date...</span>}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar mode="single" selected={date} onSelect={setDate} initialFocus />
                  </PopoverContent>
                </Popover>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant={"outline"} className={cn("w-full justify-start text-left font-normal", !endDate && "text-muted-foreground")}>
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {endDate ? format(endDate, "PPP") : <span>End date...</span>}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0" align="start">
                    <Calendar mode="single" selected={endDate} onSelect={setEndDate} initialFocus />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Include Emotions</Label>
              <div className="grid grid-cols-2 gap-2 pt-2">
                {ALL_EMOTIONS.map(emotion => (
                   <div key={emotion} className="flex items-center space-x-2">
                      <Checkbox id={emotion} checked={selectedEmotions.includes(emotion)} onCheckedChange={(checked) => handleEmotionChange(emotion, !!checked)} />
                      <Label htmlFor={emotion} className="text-sm font-normal capitalize">{emotion}</Label>
                    </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <Button onClick={handleGenerateReport} disabled={isLoading}>
              {isLoading ? "Generating..." : "Generate Report"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {generatedReport && reportData && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">
              {reportData.reportMetadata.reportTitle}
              {` (${reportData.reportMetadata.dateRangeFormatted})`}
            </h3>
          </div>
          <Tabs key={defaultTab} defaultValue={defaultTab} className="space-y-4">
            <TabsList>
              {(hasEmotionCharts || hasAttributeCharts) && <TabsTrigger value="charts">Charts</TabsTrigger>}
              {hasTables && <TabsTrigger value="tables">Tables</TabsTrigger>}
              {(reportData.insights?.length ?? 0) > 0 && <TabsTrigger value="insights">Insights</TabsTrigger>}
            </TabsList>
            
            {(hasEmotionCharts || hasAttributeCharts) && (
                <TabsContent value="charts" className="space-y-4">
                  {hasEmotionCharts && <div className="grid gap-4 md:grid-cols-2">
                    <Card><CardHeader><Tabs defaultValue={distributionRange} onValueChange={(value) => setDistributionRange(value as any)} className="w-full"><div className="flex items-center justify-between"><CardTitle>Emotion Distribution</CardTitle><TabsList className="grid h-9 w-auto grid-cols-3"><TabsTrigger value="today">Today</TabsTrigger><TabsTrigger value="week">Week</TabsTrigger><TabsTrigger value="month">Month</TabsTrigger></TabsList></div></Tabs></CardHeader><CardContent><EmotionDistributionChart range={distributionRange} /></CardContent></Card>
                    <Card><CardHeader><div className="flex items-center justify-between"><CardTitle>Emotion Trends</CardTitle><Select value={selectedEmotionForTrend} onValueChange={setSelectedEmotionForTrend}><SelectTrigger className="h-9 w-[120px]"><SelectValue /></SelectTrigger><SelectContent>{reportData.charts!.emotionTrends!.series.map(s => (<SelectItem key={s.name} value={s.name.toLowerCase()} className="capitalize">{s.name}</SelectItem>))}</SelectContent></Select></div></CardHeader><CardContent className="h-[350px] pt-4"><ForecastChart chartData={transformedTrendData} emotion={selectedEmotionForTrend} /></CardContent></Card>
                  </div>}
                  {attributeDistribution && hasAttributeCharts && (
                    <AttributeDistributionSummary data={attributeDistribution} />
                  )}
                </TabsContent>
            )}
            
            {hasTables && (
                <TabsContent value="tables" className="space-y-4">
                  {(reportData.tables?.dailySummary?.length ?? 0) > 0 && <Card><CardHeader><CardTitle>Emotion Data Summary</CardTitle><CardDescription>Tabular data for the selected time period</CardDescription></CardHeader><CardContent><div className="rounded-md border"><table className="w-full text-sm"><thead><tr className="border-b bg-muted/50 font-medium"><th className="p-3 text-left">Date</th>{Object.keys(reportData.tables!.dailySummary![0]).filter(k => k !== 'date').map(emotion => (<th key={emotion} className="p-3 text-left capitalize">{emotion}</th>))}</tr></thead><tbody>{reportData.tables!.dailySummary!.map((row, i) => (<tr key={i} className="border-b"><td className="p-3 font-medium">{row.date}</td>{Object.keys(row).filter(k => k !== 'date').map(emotion => (<td key={emotion} className="p-3">{row[emotion] || 0}</td>))}</tr>))}</tbody></table></div></CardContent></Card>}
                  {(reportData.tables?.attributeSummary?.length ?? 0) > 0 && <Card><CardHeader><CardTitle>Attribute Data Summary</CardTitle><CardDescription>Head and clothing label totals for the selected time period</CardDescription></CardHeader><CardContent><div className="rounded-md border"><table className="w-full text-sm"><thead><tr className="border-b bg-muted/50 font-medium"><th className="p-3 text-left">Type</th><th className="p-3 text-left">Label</th><th className="p-3 text-left">Count</th></tr></thead><tbody>{reportData.tables!.attributeSummary!.map((row) => (<tr key={`${row.type}-${row.label}`} className="border-b"><td className="p-3 capitalize">{row.type}</td><td className="p-3">{formatAttributeLabel(row.label)}</td><td className="p-3 font-medium">{row.count}</td></tr>))}</tbody></table></div></CardContent></Card>}
                </TabsContent>
            )}

            {(reportData.insights?.length ?? 0) > 0 && (
                <TabsContent value="insights">
                  <Card><CardHeader><CardTitle>Key Insights</CardTitle><CardDescription>Generated insights from emotion, head, and clothing data</CardDescription></CardHeader><CardContent className="space-y-4">{reportData.insights!.map((insight, i) => (<div key={i} className="rounded-lg border p-4"><div className="flex items-center gap-2"><Badge style={{ backgroundColor: insight.color, color: 'white' }}>{insight.badge}</Badge><h4 className="font-semibold">{insight.title}</h4></div><p className="mt-2 text-sm text-muted-foreground">{insight.description}</p></div>))}</CardContent></Card>
                </TabsContent>
            )}
          </Tabs>
        </div>
      )}
    </div>
  );
}
