/**
 * The artisan sales read model.
 *
 * Built in marketplace from the order event stream rather than queried from
 * checkout: "what did I sell?" is a different question from "what did this
 * buyer order?", and services do not read each other's databases. The cost is
 * that a sale appears here a moment after the order — fine for a dashboard.
 */
import { apiFetch } from "./api";

export type DailyPoint = {
  date: string;
  revenue_minor: number;
  pieces: number;
};

export type TopPiece = {
  slug: string | null;
  title: string;
  pieces: number;
  revenue_minor: number;
};

export type RecentSale = {
  order_id: string;
  slug: string | null;
  title: string;
  quantity: number;
  line_minor: number;
  currency: string;
  occurred_at: string;
};

export type SalesSummary = {
  currency: string;
  revenue_minor: number;
  pieces_sold: number;
  orders: number;
  window_days: number;
  daily: DailyPoint[];
  top_pieces: TopPiece[];
  recent: RecentSale[];
};

/** Null when the caller has no workshop, or the service cannot answer. */
export async function getSalesSummary(): Promise<SalesSummary | null> {
  try {
    const response = await apiFetch("/sales/summary");
    if (!response.ok) return null;
    return (await response.json()) as SalesSummary;
  } catch {
    return null;
  }
}
