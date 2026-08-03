"use client"

import { useState, useEffect, FormEvent } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { toast } from "sonner"
import { Cog, Save, Loader2 } from "lucide-react"

interface SettingsData {
  provider: 'local' | 'groq';
  local_endpoint_url: string;
  groq_api_key: string;
  groq_model_name: string;
}

export function ChatSettings() {
  const [settings, setSettings] = useState<SettingsData>({
    provider: 'groq',
    local_endpoint_url: '',
    groq_api_key: '',
    // --- DIUBAH: Default ke model Llama 3.1 yang baru ---
    groq_model_name: 'llama-3.1-8b-instant', 
  });
  const [isLoading, setIsLoading] = useState(true);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_NLP_API_BASE_URL ?? "http://127.0.0.1:5003"}/api/settings`);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to load settings from the server.");
      }
      const data = await response.json();
      setSettings(data);
    } catch (error: any) {
      console.error("Error fetching settings:", error);
      toast.error("Failed to load settings", { description: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = e.target;
    setSettings(prev => ({ ...prev, [id]: value }));
  };

  const handleProviderChange = (value: 'local' | 'groq') => {
    setSettings(prev => ({ ...prev, provider: value }));
  };
  
  const handleModelChange = (value: string) => {
    setSettings(prev => ({ ...prev, groq_model_name: value }));
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_NLP_API_BASE_URL ?? "http://127.0.0.1:5003"}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to save settings.");
      }
      await response.json();
      toast.success("Settings saved successfully!", {
        description: "The configuration has been updated."
      });
      
      await fetchSettings(); 
    } catch (error: any) {
      console.error("Error saving settings:", error);
      toast.error("Failed to save settings", { description: error.message });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Card className="md:flex flex-col hidden">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Cog className="h-5 w-5 text-muted-foreground"/> Chatbot Settings</CardTitle>
        <CardDescription>Select a model provider and enter the required credentials.</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && !settings.provider ? (
            <div className="flex items-center justify-center h-40">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        ) : (
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="provider">Provider Model</Label>
              <Select value={settings.provider} onValueChange={handleProviderChange} required>
                <SelectTrigger id="provider">
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="local">Local (Endpoint)</SelectItem>
                  <SelectItem value="groq">Groq</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {settings.provider === 'local' && (
              <div className="space-y-2">
                <Label htmlFor="local_endpoint_url">Local Endpoint URL</Label>
                <Input
                  id="local_endpoint_url"
                  placeholder="http://IP-LAPTOP-BACKEND:5003/chat/completions"
                  value={settings.local_endpoint_url}
                  onChange={handleInputChange}
                  required
                />
              </div>
            )}

            {settings.provider === 'groq' && (
              <> 
                <div className="space-y-2">
                  <Label htmlFor="groq_api_key">Groq API Key</Label>
                  <Input
                    id="groq_api_key"
                    type="password"
                    placeholder="gsk_..."
                    value={settings.groq_api_key}
                    onChange={handleInputChange}
                    required
                  />
                </div>
                
                <div className="space-y-2">
                  <Label htmlFor="groq_model_name">Model Groq</Label>
                  <Select value={settings.groq_model_name} onValueChange={handleModelChange} required>
                    <SelectTrigger id="groq_model_name">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    {/* --- DIUBAH: Daftar model diperbarui --- */}
                    <SelectContent>
                      <SelectItem value="llama-3.1-8b-instant">Llama 3.1 (8B Instant)</SelectItem>
                      {/* <SelectItem value="llama-3.1-70b-versatile">Llama 3.1 (70B Versatile)</SelectItem>
                      <SelectItem value="mixtral-8x7b-32768">Mixtral (8x7B)</SelectItem>
                      <SelectItem value="gemma-7b-it">Gemma (7B)</SelectItem> */}
                    </SelectContent>
                  </Select>
                </div>
              </> 
            )}
            
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin"/> : <Save className="mr-2 h-4 w-4"/>}
              {isLoading ? "Saving..." : "Save Settings"}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  )
}
