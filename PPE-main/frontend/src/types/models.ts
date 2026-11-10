export interface ModelItem {
  model_id: string;
  display_name: string;
  repo_id: string;
  filename: string;
  description: string;
  is_active: boolean;
  is_default: boolean;
  num_classes: number;
  classes?: Record<number | string, string>;
  positive_mask_support: boolean;
  positive_glove_support: boolean;
  supported_ppe: string[];
}

export interface ModelListResponse {
  total_models: number;
  active_model_id: string;
  models: ModelItem[];
}

export interface ModelSelectResponse {
  success: boolean;
  message: string;
  active_model_id: string;
  active_model: Record<string, unknown>;
}

