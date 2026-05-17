import type { RequestClient } from "../core.js";
import type { EvalBody, EvalResponse } from "../types/index.js";

export class EvaluationsResource {
  constructor(private readonly _client: RequestClient) {}

  run(body: EvalBody): Promise<EvalResponse> {
    return this._client._request("POST", "/v1/evaluation", { json: body });
  }
}
