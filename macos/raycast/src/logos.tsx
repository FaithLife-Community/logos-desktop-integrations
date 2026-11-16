import { Action, ActionPanel, getPreferenceValues, Icon, List, showToast, Toast } from "@raycast/api";
import { execFile } from "node:child_process";
import { join } from "node:path";
import { useEffect, useState } from "react";

type Result = { id: string; title: string; subtitle: string; url: string };
export default function LogosSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const { hostPath } = getPreferenceValues<{ hostPath: string }>();
  useEffect(() => {
    let cancelled = false;
    let child: ReturnType<typeof execFile> | undefined;
    setResults([]);
    if (!query.trim()) { setLoading(false); return; }
    setLoading(true);
    const timer = setTimeout(() => {
      child = execFile(join(hostPath, "Contents/MacOS/LogosDesktopIntegrations"), ["--query-json", query],
        { timeout: 10000, maxBuffer: 1024 * 1024 }, (error, stdout) => {
          if (cancelled) return;
          setLoading(false);
          if (error) { void showToast({ style: Toast.Style.Failure, title: "Cannot query Logos integrations", message: error.message }); return; }
          try { setResults(JSON.parse(stdout)); }
          catch { void showToast({ style: Toast.Style.Failure, title: "Invalid search response" }); }
        });
    }, 200);
    return () => { cancelled = true; clearTimeout(timer); child?.kill(); };
  }, [query, hostPath]);
  return <List isLoading={loading} onSearchTextChange={setQuery} filtering={false}
    searchBarPlaceholder="o John 3:16 · ol bavinck · fb Moses · lay · rp · cv John 3:16">
    <List.EmptyView icon={Icon.Book} title="Search Logos" description="Type a command or reference. Data-derived results require the full build running in the background." />
    {results.map(result => <List.Item key={result.id} title={result.title} subtitle={result.subtitle} icon={Icon.Book}
      actions={<ActionPanel><Action.Open title="Open in Logos" target={result.url} /></ActionPanel>} />)}
  </List>;
}
