export type FavoriteQuestion = {
  id: number;
  question: string;
  created_at?: string;
};

export type CatalogMetric = {
  name: string;
  unit: string;
  definition: string;
};

export type DataTableSummary = {
  table: string;
  description: string;
  count: number;
};

export type WorkbenchCatalog = {
  metrics: Record<string, CatalogMetric>;
  dimensions: Record<string, unknown>;
  values: Record<string, string[]>;
  dataset: {
    start_date: string;
    cutoff_date: string;
    counts: Record<string, number>;
  };
  data_tables: DataTableSummary[];
  model: { name: string; available: string[]; configured: boolean };
  examples: string[];
};
