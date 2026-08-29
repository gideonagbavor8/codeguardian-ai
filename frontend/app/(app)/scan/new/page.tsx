"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Upload, Github, Loader2, FileCode } from "lucide-react";
import { scanApi } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/hooks/use-toast";

export default function NewScanPage() {
  const { token } = useAuth();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  // Upload tab
  const [projectName, setProjectName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  // GitHub tab
  const [ghProject, setGhProject] = useState("");
  const [ghUrl, setGhUrl] = useState("");
  const [ghBranch, setGhBranch] = useState("main");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !file) return;
    setError(null);
    setLoading(true);
    try {
      const scan = await scanApi.uploadFile(token, file, projectName || file.name);
      toast({ title: "Scan started", description: `Scanning ${scan.project_name}…` });
      router.push(`/scan/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGithub = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      const scan = await scanApi.scanGithub(token, ghUrl, ghBranch, ghProject || ghUrl);
      toast({ title: "Scan started", description: `Cloning and scanning ${ghUrl}…` });
      router.push(`/scan/${scan.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "GitHub scan failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-xl font-semibold">New Scan</h2>
        <p className="text-sm text-muted-foreground">
          Upload a ZIP file or provide a GitHub repository URL
        </p>
      </div>

      <Tabs defaultValue="upload">
        <TabsList className="w-full">
          <TabsTrigger value="upload" className="flex-1">
            <Upload className="h-4 w-4 mr-2" /> Upload ZIP
          </TabsTrigger>
          <TabsTrigger value="github" className="flex-1">
            <Github className="h-4 w-4 mr-2" /> GitHub URL
          </TabsTrigger>
        </TabsList>

        {/* Upload tab */}
        <TabsContent value="upload">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Upload project ZIP</CardTitle>
              <CardDescription>
                Compress your project folder into a .zip file and upload it here
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpload} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="project-name">Project name (optional)</Label>
                  <Input
                    id="project-name"
                    placeholder="my-awesome-api"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>ZIP file</Label>
                  <div
                    className="border-2 border-dashed border-border rounded-lg p-8 flex flex-col items-center gap-3 cursor-pointer hover:border-primary/50 transition-colors"
                    onClick={() => fileRef.current?.click()}
                  >
                    <FileCode className="h-8 w-8 text-muted-foreground" />
                    {file ? (
                      <p className="text-sm font-medium">{file.name}</p>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Click to select a .zip file
                      </p>
                    )}
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".zip"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={loading || !file}>
                  {loading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Scanning…</>
                  ) : (
                    "Start scan"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* GitHub tab */}
        <TabsContent value="github">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Scan GitHub repository</CardTitle>
              <CardDescription>
                Provide a public GitHub repository URL to clone and scan
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleGithub} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="gh-project">Project name (optional)</Label>
                  <Input
                    id="gh-project"
                    placeholder="my-repo"
                    value={ghProject}
                    onChange={(e) => setGhProject(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="gh-url">Repository URL</Label>
                  <Input
                    id="gh-url"
                    placeholder="https://github.com/owner/repo"
                    value={ghUrl}
                    onChange={(e) => setGhUrl(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="gh-branch">Branch</Label>
                  <Input
                    id="gh-branch"
                    placeholder="main"
                    value={ghBranch}
                    onChange={(e) => setGhBranch(e.target.value)}
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={loading || !ghUrl}>
                  {loading ? (
                    <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Scanning…</>
                  ) : (
                    "Start scan"
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
