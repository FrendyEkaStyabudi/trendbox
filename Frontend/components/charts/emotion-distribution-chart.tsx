// src/components/charts/emotion-distribution-chart.tsx
"use client";

import { useEffect, useState } from "react";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
  ChartData
} from "chart.js";
import { useTheme } from "next-themes"; // Opsional, untuk tema

// Registrasi komponen Chart.js yang WAJIB digunakan
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

type DistributionDataItem = {
  category?: string;
  emotion?: string;
  label?: string;
  count: number;
};

type EmotionDistributionChartProps = {
  range: "today" | "week" | "month"; // Prop untuk rentang waktu
  metric?: "emotion" | "head" | "clothing";
};

// const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://dmpkenvfix-1091079456692.asia-southeast2.run.app";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:5000";

// Warna dasar untuk chart emosi (bisa diperluas)
const EMOTION_CHART_COLORS: Record<string, { background: string; border: string }> = {
  happy: { background: 'rgba(255, 206, 86, 0.6)', border: 'rgba(255, 206, 86, 1)' },
  sad: { background: 'rgba(54, 162, 235, 0.6)', border: 'rgba(54, 162, 235, 1)' },
  angry: { background: 'rgba(255, 99, 132, 0.6)', border: 'rgba(255, 99, 132, 1)' },
  neutral: { background: 'rgba(201, 203, 207, 0.6)', border: 'rgba(201, 203, 207, 1)' },
  surprised: { background: 'rgba(153, 102, 255, 0.6)', border: 'rgba(153, 102, 255, 1)' },
  scared: { background: 'rgba(255, 159, 64, 0.6)', border: 'rgba(255, 159, 64, 1)' },
  fear: { background: 'rgba(75, 192, 192, 0.6)', border: 'rgba(75, 192, 192, 1)' },
  default: { background: 'rgba(128, 128, 128, 0.6)', border: 'rgba(128, 128, 128, 1)' }
};

const ATTRIBUTE_CHART_COLORS = [
  { background: 'rgba(139, 92, 246, 0.6)', border: 'rgba(139, 92, 246, 1)' },
  { background: 'rgba(20, 184, 166, 0.6)', border: 'rgba(20, 184, 166, 1)' },
  { background: 'rgba(249, 115, 22, 0.6)', border: 'rgba(249, 115, 22, 1)' },
  { background: 'rgba(59, 130, 246, 0.6)', border: 'rgba(59, 130, 246, 1)' },
  { background: 'rgba(236, 72, 153, 0.6)', border: 'rgba(236, 72, 153, 1)' },
];

const getEmotionChartColor = (emotion: string, index = 0) => {
    return EMOTION_CHART_COLORS[emotion.toLowerCase()] || ATTRIBUTE_CHART_COLORS[index % ATTRIBUTE_CHART_COLORS.length];
}

export default function EmotionDistributionChart({ range, metric = "emotion" }: EmotionDistributionChartProps) {
  const [chartData, setChartData] = useState<ChartData<'bar'>>({ labels: [], datasets: [] });
  const [isLoading, setIsLoading] = useState(true);
  const { theme } = useTheme(); // Opsional

  useEffect(() => {
    setIsLoading(true);
    // Menggunakan prop `range` untuk fetch data
    fetch(`${API_BASE_URL}/api/distribution?range=${range}&metric=${metric}`)
      .then((res) => {
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
      })
      .then((apiData: DistributionDataItem[]) => {
        if (!apiData || apiData.length === 0) {
          setChartData({ labels: [], datasets: [] });
          return;
        }
        const categories = apiData.map((d) => d.category ?? d.emotion ?? d.label ?? "unknown");
        const labels = categories.map((category) =>
          category.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
        );
        const dataCounts = apiData.map((d) => d.count);
        const backgroundColors = categories.map((category, index) => getEmotionChartColor(category, index).background);
        const borderColors = categories.map((category, index) => getEmotionChartColor(category, index).border);

        setChartData({
          labels,
          datasets: [
            {
              label: "Count",
              data: dataCounts,
              backgroundColor: backgroundColors,
              borderColor: borderColors,
              borderWidth: 1,
              borderRadius: 4,
              barPercentage: 0.6,
              categoryPercentage: 0.7,
            },
          ],
        });
      })
      .catch((err) => {
        console.error(`Error fetching distribution for ${range}:`, err);
        setChartData({ labels: ["Error"], datasets: [{ label: "Error loading data", data: [], backgroundColor: 'rgba(255,99,132,0.2)'}] });
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [range, metric]); // useEffect akan berjalan lagi jika `range` berubah

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      title: { display: false },
      tooltip: { /* Styling tooltip bisa ditambahkan di sini, contoh dari versi saya sebelumnya */ }
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)' }, // Opsional tema
        ticks: { 
            color: theme === 'dark' ? '#9ca3af' : '#6b7280', // Opsional tema
            precision: 0 
        },
      },
      x: {
        grid: { display: false },
        ticks: { color: theme === 'dark' ? '#9ca3af' : '#6b7280' }, // Opsional tema
      }
    },
  };
  
  if (isLoading) {
    return <div style={{ height: "300px" }} className="flex items-center justify-center text-sm text-muted-foreground">Loading chart...</div>;
  }

  if (!chartData.datasets.length || !chartData.datasets[0]?.data?.length) {
    return <div style={{ height: "300px" }} className="flex items-center justify-center text-sm text-muted-foreground">No data available for {range}.</div>;
  }

  return (
    <div style={{ height: "300px" /* Sesuaikan tinggi jika perlu */ }}>
      <Bar data={chartData} options={options} />
    </div>
  );
}
