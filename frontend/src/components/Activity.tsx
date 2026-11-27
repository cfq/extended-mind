import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";

import { api } from "../lib/api";
import { type ItemSummary, displayTitle, itemsKey } from "../lib/items";

type StepState =
  | "pending"
  | "queued"
  | "running"
  | "ok"
  | "failed"
  | "skipped"
  | "blocked"
  | "no_content";

type Step = {
  name: string;
  state: StepState;
  message: string;
  finished_at: string | null;
};

type ActivityRow = ItemSummary & { steps: Step[] };

const LIMIT = 20;
const activityKey = ["activity"];
// While anything is unfinished, the table follows it.
const REFRESH_MS = 3000;
const UNFINISHED: StepState[] = ["pending", "queued", "running"];
// Already picked up: a retry now would run it twice.
const IN_PROGRESS: StepState[] = ["queued", "running"];

const words = (name: string) => name.replaceAll("_", " ");

function shortUrl(url: string): string {
  return url.replace(/^https?:\/\/(www\.)?/, "");
}

function badgeTitle(step: Step): string {
  if (IN_PROGRESS.includes(step.state)) return `${words(step.name)}: ${step.state}`;
  const when = step.finished_at ? new Date(step.finished_at).toLocaleString() : "";
  const detail = [step.message, when].filter(Boolean).join(" · ");
  return `${detail ? `${detail}\n` : ""}Retry ${words(step.name)}`;
}

// The newest items and how each step went. Click a badge to retry that
// step and everything that depends on it.
export function Activity() {
  const queryClient = useQueryClient();

  const { data: rows, error } = useQuery({
    queryKey: activityKey,
    queryFn: () => api<ActivityRow[]>(`/items/activity?limit=${LIMIT}`),
    refetchInterval: (query) =>
      query.state.data?.some((row) => row.steps.some((s) => UNFINISHED.includes(s.state)))
        ? REFRESH_MS
        : false,
  });

  const retry = useMutation({
    mutationFn: ({ id, step }: { id: string; step: string }) =>
      api<ActivityRow>(`/items/${id}/steps/${step}/retry`, { method: "POST" }),
    onSuccess: (updated) => {
      queryClient.setQueryData<ActivityRow[]>(activityKey, (old) =>
        old?.map((row) => (row.id === updated.id ? updated : row)),
      );
      queryClient.invalidateQueries({ queryKey: itemsKey });
    },
    // Someone else's retry got there first: show the current state.
    onError: () => queryClient.invalidateQueries({ queryKey: activityKey }),
  });

  if (error) return <p className="error">{error.message}</p>;
  if (!rows) return null;
  if (rows.length === 0) return <p>Nothing saved yet.</p>;

  return (
    <div className="activity-wrap">
      {retry.error && <p className="error">{retry.error.message}</p>}
      <table className="activity">
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className="activity-title">
                <Link to={`/item/${row.id}`}>{displayTitle(row)}</Link>
              </td>
              <td className="activity-source">
                {row.thumbnail ? (
                  <img src={row.thumbnail} alt="" loading="lazy" />
                ) : (
                  <span title={row.url}>{shortUrl(row.url || row.url_submitted)}</span>
                )}
              </td>
              <td>
                <ul className="badges">
                  {row.steps.map((step) => (
                    <li key={step.name}>
                      <button
                        type="button"
                        className={`badge badge-${step.state}`}
                        title={badgeTitle(step)}
                        disabled={IN_PROGRESS.includes(step.state) || retry.isPending}
                        onClick={() => retry.mutate({ id: row.id, step: step.name })}
                      >
                        <span className="badge-label">{words(step.name)}</span>
                        <span className="badge-state">{words(step.state)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
