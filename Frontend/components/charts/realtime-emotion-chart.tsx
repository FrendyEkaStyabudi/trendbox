// src/components/charts/realtime-emotion-chart.tsx
"use client";

import { useEffect, useState } from "react";
import { Line, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ChartOptions,
  ChartData,
  ScatterDataPoint, // Untuk tipe data yang lebih akurat
  BubbleDataPoint   // Untuk tipe data yang lebih akurat
} from "chart.js";
import { useTheme } from "next-themes";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

type EmotionTrendDataPoint = {
  hours?: number[];
  days?: number[];
  dates?: string[];
  counts: number[];
};

type EmotionTrendsResponse = Record<string, EmotionTrendDataPoint>;

type RealtimeEmotionChartProps = {
  weekly?: boolean;
  historical?: boolean; // Jika Anda ingin menggunakan endpoint /api/trends
  chartType?: "line" | "bar" | "area";
  isPerformance?: boolean;
  metric?: "emotion" | "head" | "clothing";
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://192.168.0.123:5000";

const EMOTION_HSL_COLORS: Record<string, string> = {
  happy: "48, 100%, 50%", sad: "205, 70%, 50%", angry: "0, 70%, 50%",
  neutral: "220, 5%, 50%", surprised: "270, 70%, 60%", scared: "30, 90%, 60%",
  fear: "120, 60%, 45%", default: "210, 10%, 40%"
};

const distinctColorsCycle = [
    "48, 100%, 50%", "205, 70%, 50%", "0, 70%, 50%", "270, 70%, 60%",
    "30, 90%, 60%", "120, 60%, 45%", "300, 70%, 60%", "180, 60%, 45%",
];

const getEmotionHSLColor = (emotion: string, index: number): string => {
    const lowerEmotion = emotion.toLowerCase();
    if (EMOTION_HSL_COLORS[lowerEmotion]) {
        return EMOTION_HSL_COLORS[lowerEmotion];
    }
    return distinctColorsCycle[index % distinctColorsCycle.length];
};

export default function RealtimeEmotionChart({
  weekly = false,
  historical = false,
  chartType = "line",
  metric = "emotion",
}: RealtimeEmotionChartProps) {
  const [chartData, setChartData] = useState<ChartData<'line' | 'bar'>>({ labels: [], datasets: [] });
  const [isLoading, setIsLoading] = useState(true);
  const { theme } = useTheme();

  useEffect(() => {
    setIsLoading(true);
    let endpoint = `${API_BASE_URL}/api/trends/today`;
    if (weekly) {
      endpoint = `${API_BASE_URL}/api/trends/weekly`;
    } else if (historical) {
      endpoint = `${API_BASE_URL}/api/trends`; // Endpoint untuk semua data harian historis
    }
    endpoint += `${endpoint.includes("?") ? "&" : "?"}metric=${metric}`;
    
    fetch(endpoint)
      .then((res) => {
        if (!res.ok) throw new Error(`API error: ${res.status} from ${endpoint}`);
        return res.json();
      })
      .then((apiData: EmotionTrendsResponse) => {
        if (Object.keys(apiData).length === 0) {
            setChartData({ labels: [], datasets: [] });
            return;
        }

        let labels: string[] = [];
        let timeDataKey: 'hours' | 'days' | 'dates' = 'hours';

        if (weekly) {
          labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
          timeDataKey = 'days';
        } else if (historical) {
          const allDatesSet = new Set<string>();
          Object.values(apiData).forEach(emotionData => {
            emotionData.dates?.forEach(date => allDatesSet.add(date));
          });
          labels = Array.from(allDatesSet).sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
          timeDataKey = 'dates';
        } else {
          labels = Array.from({ length: 24 }, (_, i) => `${i}:00`);
          timeDataKey = 'hours';
        }

        const datasets = Object.entries(apiData).map(([emotion, values], i) => {
          const baseColorHSL = getEmotionHSLColor(emotion, i);
          
          const dataPoints = labels.map((labelOrIndexRef, indexInLabelsArray) => {
            let valueIndex = -1;
            // `indexInLabelsArray` adalah 0-6 untuk mingguan (Senin-Minggu) atau 0-23 untuk harian (jam)
            // Ini cocok dengan output `day_of_week` (0-6) atau `hour` (0-23) dari API
            const refIndex = (timeDataKey === 'dates') ? labelOrIndexRef : indexInLabelsArray;

            if (timeDataKey === 'hours') {
              valueIndex = values.hours?.indexOf(refIndex as number) ?? -1;
            } else if (timeDataKey === 'days') {
              valueIndex = values.days?.indexOf(refIndex as number) ?? -1;
            } else if (timeDataKey === 'dates') {
               valueIndex = values.dates?.indexOf(refIndex as string) ?? -1;
            }
            return (valueIndex !== -1 && values.counts) ? values.counts[valueIndex] : 0;
          });

          return {
            label: emotion.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
            data: dataPoints,
            borderColor: `hsl(${baseColorHSL})`,
            backgroundColor: chartType === 'area' ? `hsla(${baseColorHSL}, 0.3)` : `hsl(${baseColorHSL})`,
            fill: chartType === 'area',
            tension: 0.3,
            pointBackgroundColor: `hsl(${baseColorHSL})`,
            pointBorderColor: theme === 'dark' ? '#1f2937' : '#ffffff',
            pointHoverBackgroundColor: `hsl(${baseColorHSL})`,
            pointHoverBorderColor: `hsl(${baseColorHSL})`,
            borderWidth: chartType === 'bar' ? 0 : 2,
            barPercentage: 0.7,
            categoryPercentage: 0.8,
          };
        });
        setChartData({ labels, datasets });
      })
      .catch((err) => {
        console.warn(`[RealtimeEmotionChart] Backend offline or starting up:`, err?.message || err);
        setChartData({ labels: ["No Data"], datasets: [{ label: "Data Offline", data: [], backgroundColor: 'rgba(255,99,132,0.2)'}] });
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [weekly, historical, chartType, theme, metric]);

  const options: ChartOptions<'line' | 'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: "top",
        labels: { color: theme === 'dark' ? '#e5e7eb' : '#4b5563', usePointStyle: true, boxWidth: 8 }
      },
      title: { display: false },
      tooltip: {
        backgroundColor: theme === 'dark' ? '#27272a' : '#ffffff',
        titleColor: theme === 'dark' ? '#f8fafc' : '#020617',
        bodyColor: theme === 'dark' ? '#e2e8f0' : '#334155',
        borderColor: theme === 'dark' ? '#3f3f46' : '#e5e7eb',
        borderWidth: 1, padding: 10, usePointStyle: true,
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' },
        ticks: { color: theme === 'dark' ? '#9ca3af' : '#6b7280', precision: 0 },
      },
      x: {
        grid: { color: theme === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
        ticks: { color: theme === 'dark' ? '#9ca3af' : '#6b7280' },
      },
    },
  };

  if (isLoading) {
    return <div style={{ height: "350px" }} className="flex items-center justify-center text-sm text-muted-foreground">Loading chart...</div>;
  }

  // Perbaikan untuk TS18047 & TS2365 (line 170 di error report Anda)
  const hasValidData = chartData.datasets.some(ds =>
    ds.data?.some(dataPoint => {
        // Memeriksa apakah dataPoint adalah angka dan lebih besar dari 0
        // atau jika itu adalah objek ScatterDataPoint/BubbleDataPoint dengan y > 0
        if (typeof dataPoint === 'number') {
            return dataPoint > 0;
        }
        if (dataPoint && typeof (dataPoint as ScatterDataPoint).y === 'number') {
            return (dataPoint as ScatterDataPoint).y > 0;
        }
        return false;
    })
  );

  if (!chartData.datasets.length || !hasValidData) {
    let message = "No data available for today's trends.";
    if (weekly) message = "No data available for this week's trends.";
    if (historical) message = "No historical trend data available.";
    return <div style={{ height: "350px" }} className="flex items-center justify-center text-sm text-muted-foreground">{message}</div>;
  }
  
  const ChartComponent = chartType === 'bar' ? Bar : Line;

  return (
    <div style={{ height: "350px" }}>
      <ChartComponent data={chartData as any} options={options} />
    </div>
  );
}
