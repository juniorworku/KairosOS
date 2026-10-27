import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "./auth";
import {
  api,
  replayQueue,
  resetFailedQueue,
  discardFailedQueue,
} from "../api/client";
export function useData<T>(path: string, enabled = true) {
  const { user } = useAuth();
  return useQuery({
    queryKey: [user?.id || "anonymous", path],
    queryFn: () => api<T>(path),
    enabled,
    networkMode: "always",
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
  const { user } = useAuth();
  const online = useOnline();
  const client = useQueryClient();
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    setError(undefined);
    if (online)
      void replayQueue()
        .then(() => client.invalidateQueries())
        .catch(setError);
  }, [online, client, user?.id]);
  return {
    error,
    retry: async () => {
      setError(undefined);
      await resetFailedQueue();
      try {
        await replayQueue();
        await client.invalidateQueries();
      } catch (error) {
        setError(error);
      }
    },
    discard: async () => {
      await discardFailedQueue();
      setError(undefined);
    },
  };
}
