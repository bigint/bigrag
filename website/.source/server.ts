// @ts-nocheck
import * as __fd_glob_25 from "../content/docs/sdks/typescript.mdx?collection=docs"
import * as __fd_glob_24 from "../content/docs/sdks/python.mdx?collection=docs"
import * as __fd_glob_23 from "../content/docs/getting-started/quickstart.mdx?collection=docs"
import * as __fd_glob_22 from "../content/docs/getting-started/installation.mdx?collection=docs"
import * as __fd_glob_21 from "../content/docs/getting-started/configuration.mdx?collection=docs"
import * as __fd_glob_20 from "../content/docs/deployment/production.mdx?collection=docs"
import * as __fd_glob_19 from "../content/docs/deployment/docker.mdx?collection=docs"
import * as __fd_glob_18 from "../content/docs/concepts/webhooks.mdx?collection=docs"
import * as __fd_glob_17 from "../content/docs/concepts/search.mdx?collection=docs"
import * as __fd_glob_16 from "../content/docs/concepts/embeddings.mdx?collection=docs"
import * as __fd_glob_15 from "../content/docs/concepts/documents.mdx?collection=docs"
import * as __fd_glob_14 from "../content/docs/concepts/collections.mdx?collection=docs"
import * as __fd_glob_13 from "../content/docs/api-reference/webhooks.mdx?collection=docs"
import * as __fd_glob_12 from "../content/docs/api-reference/vectors.mdx?collection=docs"
import * as __fd_glob_11 from "../content/docs/api-reference/query.mdx?collection=docs"
import * as __fd_glob_10 from "../content/docs/api-reference/health.mdx?collection=docs"
import * as __fd_glob_9 from "../content/docs/api-reference/documents.mdx?collection=docs"
import * as __fd_glob_8 from "../content/docs/api-reference/collections.mdx?collection=docs"
import * as __fd_glob_7 from "../content/docs/api-reference/authentication.mdx?collection=docs"
import * as __fd_glob_6 from "../content/docs/index.mdx?collection=docs"
import { default as __fd_glob_5 } from "../content/docs/sdks/meta.json?collection=docs"
import { default as __fd_glob_4 } from "../content/docs/getting-started/meta.json?collection=docs"
import { default as __fd_glob_3 } from "../content/docs/deployment/meta.json?collection=docs"
import { default as __fd_glob_2 } from "../content/docs/concepts/meta.json?collection=docs"
import { default as __fd_glob_1 } from "../content/docs/api-reference/meta.json?collection=docs"
import { default as __fd_glob_0 } from "../content/docs/meta.json?collection=docs"
import { server } from 'fumadocs-mdx/runtime/server';
import type * as Config from '../source.config';

const create = server<typeof Config, import("fumadocs-mdx/runtime/types").InternalTypeConfig & {
  DocData: {
  }
}>({"doc":{"passthroughs":["extractedReferences"]}});

export const docs = await create.docs("docs", "content/docs", {"meta.json": __fd_glob_0, "api-reference/meta.json": __fd_glob_1, "concepts/meta.json": __fd_glob_2, "deployment/meta.json": __fd_glob_3, "getting-started/meta.json": __fd_glob_4, "sdks/meta.json": __fd_glob_5, }, {"index.mdx": __fd_glob_6, "api-reference/authentication.mdx": __fd_glob_7, "api-reference/collections.mdx": __fd_glob_8, "api-reference/documents.mdx": __fd_glob_9, "api-reference/health.mdx": __fd_glob_10, "api-reference/query.mdx": __fd_glob_11, "api-reference/vectors.mdx": __fd_glob_12, "api-reference/webhooks.mdx": __fd_glob_13, "concepts/collections.mdx": __fd_glob_14, "concepts/documents.mdx": __fd_glob_15, "concepts/embeddings.mdx": __fd_glob_16, "concepts/search.mdx": __fd_glob_17, "concepts/webhooks.mdx": __fd_glob_18, "deployment/docker.mdx": __fd_glob_19, "deployment/production.mdx": __fd_glob_20, "getting-started/configuration.mdx": __fd_glob_21, "getting-started/installation.mdx": __fd_glob_22, "getting-started/quickstart.mdx": __fd_glob_23, "sdks/python.mdx": __fd_glob_24, "sdks/typescript.mdx": __fd_glob_25, });