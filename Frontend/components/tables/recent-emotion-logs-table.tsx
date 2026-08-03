// src/components/tables/recent-emotion-logs-table.tsx
"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  FilterIcon,
  UploadCloudIcon,
  SearchIcon,
  Loader2,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";

interface LogEntry {
  id?: string | number;
  timestamp: string;
  person: string;
  emotion: string;
  confidence: number;
}

interface ActiveFilters {
  emotions: string[];
}

const API_BASE_URL =
  // process.env.NEXT_PUBLIC_API_BASE_URL ?? "https://dmpkenvfix-1091079456692.asia-southeast2.run.app";
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:5000";

const emotionDisplayConfig: Record<string, { className: string }> = {
  happy: { className: "bg-orange-500 text-white border-orange-600" },
  sad: { className: "bg-blue-500 text-white border-blue-600" },
  angry: { className: "bg-red-600 text-white border-red-700" },
  neutral: { className: "bg-slate-500 text-white border-slate-600" },
  surprised: { className: "bg-purple-500 text-white border-purple-600" },
  scared: { className: "bg-pink-500 text-white border-pink-600" },
  fear: { className: "bg-lime-500 text-lime-950 border-lime-600" },
  disgust: { className: "bg-teal-500 text-white border-teal-600" },
  default: { className: "bg-gray-500 text-white border-gray-600" },
};

const getEmotionBadgeStyle = (emotion: string): string => {
  return (
    emotionDisplayConfig[emotion.toLowerCase()]?.className ||
    emotionDisplayConfig.default.className
  );
};

const formatLogTime = (timestamp: string): string => {
  try {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    });
  } catch (error) {
    return "Invalid Time";
  }
};

const formatConfidence = (confidence: number): string => {
  return `${Math.round(confidence * 100)}%`;
};

const ITEMS_PER_PAGE = 10;

export default function RecentEmotionLogsTable() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [isFilterDialogOpen, setIsFilterDialogOpen] = useState(false);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({
    emotions: [],
  });
  const [tempFilters, setTempFilters] = useState<ActiveFilters>({
    ...activeFilters,
  });
  const [currentPage, setCurrentPage] = useState(1);

  const availableEmotions = useMemo(() => {
    const emotionSet = new Set(logs.map((log) => log.emotion));
    return Array.from(emotionSet).sort();
  }, [logs]);

  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(`${API_BASE_URL}/api/logs`);
        if (!response.ok) {
          throw new Error(
            `Failed to fetch logs: ${response.status} ${response.statusText}`
          );
        }
        const data: LogEntry[] = await response.json();
        const formattedData = data.map((log) => ({
          ...log,
          timestamp: String(log.timestamp),
        }));
        setLogs(formattedData);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unknown error occurred while fetching logs.");
        }
      } finally {
        setIsLoading(false);
      }
    };
    fetchLogs();
  }, []);

  const filteredLogs = useMemo(() => {
    let filtered = logs;

    if (activeFilters.emotions.length > 0) {
      filtered = filtered.filter((log) =>
        activeFilters.emotions.includes(log.emotion)
      );
    }

    if (searchTerm.trim()) {
      const lowerSearchTerm = searchTerm.toLowerCase().trim();
      filtered = filtered.filter(
        (log) =>
          (log.emotion?.toLowerCase() || "").includes(lowerSearchTerm) ||
          formatLogTime(log.timestamp).toLowerCase().includes(lowerSearchTerm) ||
          formatConfidence(log.confidence).toLowerCase().includes(lowerSearchTerm)
      );
    }
    
    setCurrentPage(1);
    return filtered;
  }, [logs, searchTerm, activeFilters]);

  const paginatedLogs = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    const endIndex = startIndex + ITEMS_PER_PAGE;
    return filteredLogs.slice(startIndex, endIndex);
  }, [filteredLogs, currentPage]);

  const totalPages = Math.ceil(filteredLogs.length / ITEMS_PER_PAGE);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const handleApplyFilters = () => {
    setActiveFilters(tempFilters);
    setIsFilterDialogOpen(false);
  };

  const handleClearFilters = () => {
    const clearedFilters = { emotions: [] };
    setTempFilters(clearedFilters);
    setActiveFilters(clearedFilters);
    setIsFilterDialogOpen(false);
  };

  const handleEmotionToggle = (
    emotion: string,
    checked: boolean | "indeterminate"
  ) => {
    setTempFilters((prev) => {
      const newEmotions = checked
        ? [...prev.emotions, emotion]
        : prev.emotions.filter((e) => e !== emotion);
      return { ...prev, emotions: newEmotions };
    });
  };

  const exportToCSV = () => {
    if (filteredLogs.length === 0) {
      alert("No data to export.");
      return;
    }
    const headers = ["Time", "Emotion", "Confidence"];
    const csvRows = [
      headers.join(","),
      ...filteredLogs.map((log) =>
        [
          `"${formatLogTime(log.timestamp)}"`,
          `"${log.emotion.replace(/"/g, '""')}"`,
          `"${formatConfidence(log.confidence)}"`,
        ].join(",")
      ),
    ];
    const csvString = csvRows.join("\r\n");
    const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    if (link.download !== undefined) {
      const url = URL.createObjectURL(blob);
      link.setAttribute("href", url);
      link.setAttribute("download", "emotion_logs.csv");
      link.style.visibility = "hidden";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-60 text-muted-foreground space-y-2">
        <Loader2 className="h-8 w-8 animate-spin" />
        <span>Loading logs...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col justify-center items-center h-60 text-red-600 bg-red-50 p-4 rounded-md border border-red-200 space-y-2">
        <p className="font-semibold">Error loading logs:</p>
        <p className="text-sm">{error}</p>
        <Button
          onClick={() => window.location.reload()}
          variant="outline"
          size="sm"
          className="mt-2"
        >
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="relative w-full sm:max-w-xs">
          <SearchIcon className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={handleSearchChange}
            className="pl-8 w-full"
          />
        </div>
        <div className="flex items-center gap-2">
          <Dialog
            open={isFilterDialogOpen}
            onOpenChange={(open) => {
              if (open) setTempFilters({ ...activeFilters });
              setIsFilterDialogOpen(open);
            }}
          >
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="bg-background hover:bg-accent"
              >
                <FilterIcon className="mr-2 h-4 w-4" />
                Filter
                {activeFilters.emotions.length > 0 && (
                  <span className="ml-2 inline-block h-2 w-2 rounded-full bg-sky-500"></span>
                )}
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[480px]">
              <DialogHeader>
                <DialogTitle>Filter Logs</DialogTitle>
                <DialogDescription>
                  Apply filters to narrow down the log entries.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-6 py-4">
                <div className="space-y-2">
                  <Label htmlFor="filter-emotion" className="font-semibold">
                    Emotion
                  </Label>
                  <ScrollArea className="h-[150px] w-full rounded-md border p-3">
                    <div className="space-y-2">
                      {availableEmotions.map((emotion) => (
                        <div
                          key={emotion}
                          className="flex items-center space-x-2"
                        >
                          <Checkbox
                            id={`emotion-${emotion}`}
                            checked={tempFilters.emotions.includes(emotion)}
                            onCheckedChange={(checked) =>
                              handleEmotionToggle(emotion, checked)
                            }
                          />
                          <Label
                            htmlFor={`emotion-${emotion}`}
                            className="font-normal capitalize"
                          >
                            {emotion}
                          </Label>
                        </div>
                      ))}
                      {availableEmotions.length === 0 && (
                        <p className="text-sm text-muted-foreground">
                          No emotions to filter by.
                        </p>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </div>
              <DialogFooter className="sm:justify-between">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleClearFilters}
                >
                  Clear Filters
                </Button>
                <Button type="button" onClick={handleApplyFilters}>
                  Apply Filters
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button
            variant="outline"
            size="sm"
            className="bg-background hover:bg-accent"
            onClick={exportToCSV}
          >
            <UploadCloudIcon className="mr-2 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      <div className="rounded-md border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px] text-muted-foreground">
                Time
              </TableHead>
              <TableHead className="text-muted-foreground">Emotion</TableHead>
              <TableHead className="w-[120px] text-muted-foreground">
                Confidence
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedLogs.length > 0 ? (
              paginatedLogs.map((log, index) => (
                <TableRow
                  key={log.id || `${log.timestamp}-${index}`}
                  className="hover:bg-muted/50"
                >
                  <TableCell className="font-medium text-sm py-3">
                    {formatLogTime(log.timestamp)}
                  </TableCell>
                  <TableCell className="py-3">
                    <Badge
                      variant="default"
                      className={`border text-xs px-2.5 py-0.5 rounded-full ${getEmotionBadgeStyle(
                        log.emotion
                      )}`}
                    >
                      {log.emotion.charAt(0).toUpperCase() +
                        log.emotion.slice(1)}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm py-3">
                    {formatConfidence(log.confidence)}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="h-24 text-center text-muted-foreground"
                >
                  {searchTerm || activeFilters.emotions.length > 0
                    ? "No logs match your criteria."
                    : "No logs recorded yet."}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-end space-x-2 py-4">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
          >
            <ChevronLeftIcon className="h-4 w-4 mr-1" />
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {currentPage} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              setCurrentPage((prev) => Math.min(totalPages, prev + 1))
            }
            disabled={currentPage === totalPages}
          >
            Next
            <ChevronRightIcon className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  );
}
