import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, replayQueue } from "../api/client";
export function useData<T>(path: string, enabled = true) {
  return useQuery({
    queryKey: [path],
    queryFn: () => api<T>(path),
    enabled,
    retry: false,
  });
}
export function useWrite<T = unknown>(path: string, method = "POST") {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: unknown) => api<T>(path, method, body),
    onSuccess: async () => {
      await client.invalidateQueries();
    },
  });
}
export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}
export function useReplay() {
  const online = useOnline();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    if (online)
      void replayQueue()
        .then(() => client.invalidateQueries())
        .catch(setError);
  }, [online, client]);
  return error;
}
